import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.decomposition import PCA
import joblib
try:
    from . import database
except ImportError:
    import database
from sklearn.model_selection import cross_val_score, StratifiedKFold
import numpy as np

class ModelTrainer:

    def __init__(self, model_id, date_range, valid=0):
        self.model_id = model_id
        self.date_range = date_range
        self.required_tables = self._get_required_tables()
        self.data = self._load_data()
        self.valid = valid
        self.model = None
        self.scaler = None
        self.cv_scores = None

    def _get_required_tables(self):
        table_map = {'1': ['table_baseline', 'table_hbp'], '2': ['table_baseline', 'table_depre', 'table_psqi'], '3': ['table_baseline', 'table_depre', 'table_psqi', 'table_hbp']}
        return table_map.get(self.model_id, [])

    def _load_data(self):
        try:
            self.data = database.load_model_trainer_data(self.required_tables, self.date_range)
            if self.data is None or self.data.empty:
                raise ValueError('未能加载到任何数据，请检查数据文件是否存在且包含数据')
            print(f'成功加载数据，形状: {self.data.shape}')
            return self.data
        except Exception as e:
            print(f'加载数据失败: {str(e)}')
            raise

    def _preprocess_data(self):
        if self.data is None or self.data.empty:
            raise ValueError('没有可用的数据进行预处理')
        processed = self.data.copy()
        processed.drop(columns=['user_id'], errors='ignore', inplace=True)
        required_columns = ['age', 'height', 'weight']
        if self.model_id == '1':
            required_columns.extend(['systolic_bp', 'diastolic_bp'])
        elif self.model_id == '2':
            required_columns.extend(['depre_question_' + str(i) for i in range(1, 10)])
        elif self.model_id == '3':
            required_columns.extend(['systolic_bp', 'diastolic_bp'])
        missing_columns = [col for col in required_columns if col not in processed.columns]
        if missing_columns:
            raise ValueError(f"缺少必要的列: {', '.join(missing_columns)}")
        if 'time' in processed.columns:
            print('have time')
            processed.drop(columns='time', inplace=True)
            print(processed)
        if self.model_id == '1':
            processed['target'] = ((processed['systolic_bp'] >= 140) | (processed['diastolic_bp'] >= 90)).astype(int)
            cont_features = ['age', 'height', 'weight']
            self.scaler = StandardScaler()
            processed[cont_features] = self.scaler.fit_transform(processed[cont_features])
            return (processed.drop(columns=['target', 'systolic_bp', 'diastolic_bp']), processed['target'])
        elif self.model_id == '2':
            phq9_columns = ['depre_question_1', 'depre_question_2', 'depre_question_3', 'depre_question_4', 'depre_question_5', 'depre_question_6', 'depre_question_7', 'depre_question_8', 'depre_question_9']
            processed['phq9_score'] = processed[phq9_columns].sum(axis=1)
            processed['target'] = pd.cut(processed['phq9_score'], bins=[-1, 4, 9, 27], labels=[0, 1, 2]).astype(int)
            cont_features = ['age', 'height', 'weight']
            self.scaler = StandardScaler()
            processed[cont_features] = self.scaler.fit_transform(processed[cont_features])
            # These answers define the label, so they cannot also be predictors.
            return (processed.drop(columns=['target', 'phq9_score', *phq9_columns]), processed['target'])
        elif self.model_id == '3':
            cont_features = ['age', 'height', 'weight', 'systolic_bp', 'diastolic_bp']
            self.scaler = StandardScaler()
            processed[cont_features] = self.scaler.fit_transform(processed[cont_features])
            return (processed, None)

    def train(self):
        try:
            print(f'开始训练模型 {self.model_id}')
            print(f'使用日期范围: {self.date_range}')
            try:
                X, y = self._preprocess_data()
                classes = None
                if y is not None:
                    classes, counts = np.unique(y, return_counts=True)
                    if len(classes) < 2:
                        raise ValueError('At least two classes are required')
                    if self.valid == 1 and counts.min() < 5:
                        raise ValueError('Each class needs at least five visits for validation')
                    if self.model_id == '2':
                        y = pd.Series(np.searchsorted(classes, y), index=y.index)
                print(f'预处理后的数据形状: X={X.shape}, ' + (f'y={y.shape}' if y is not None else 'y=None'))
            except Exception as e:
                print(f'数据预处理失败: {str(e)}')
                return {'success': False, 'error': f'数据预处理失败: {str(e)}'}
            try:
                if self.model_id == '1':
                    print('训练高血压风险预测模型（随机森林）')
                    self.model = RandomForestClassifier(n_estimators=100, random_state=42)
                    self.model.fit(X, y)
                    print('特征重要性:', dict(zip(X.columns, self.model.feature_importances_)))
                elif self.model_id == '2':
                    print('训练抑郁风险预测模型（XGBoost）')
                    self.model = XGBClassifier(random_state=42)
                    self.model.fit(X, y)
                    print('特征重要性:', dict(zip(X.columns, self.model.feature_importances_)))
                elif self.model_id == '3':
                    print('训练生物年龄评估模型（PCA）')
                    self.model = PCA(n_components=3, random_state=42)
                    self.model.fit(X)
                    print('解释方差比:', self.model.explained_variance_ratio_)
            except Exception as e:
                print(f'模型训练失败: {str(e)}')
                return {'success': False, 'error': f'模型训练失败: {str(e)}'}
            try:
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                model_path = os.path.join(project_root, 'data/model', f'model_{self.model_id}.pkl')
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                model_data = {'model': self.model, 'scaler': self.scaler, 'feature_names': X.columns.tolist(), 'training_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
                if classes is not None:
                    model_data['classes'] = classes.tolist()
                joblib.dump(model_data, model_path)
                print(f'模型已保存到: {model_path}')
            except Exception as e:
                print(f'保存模型失败: {str(e)}')
                return {'success': False, 'error': f'保存模型失败: {str(e)}'}
            if self.valid == 1 and self.model_id in ['1', '2']:
                try:
                    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
                    if self.model_id == '1':
                        cv_model = RandomForestClassifier(n_estimators=100, random_state=42)
                    else:
                        cv_model = XGBClassifier(random_state=42)
                    raw, cv_model = self.validation_setup(X, cv_model)
                    scores = cross_val_score(cv_model, raw, y, cv=cv, scoring='accuracy')
                    self.cv_scores = scores.tolist()
                    print(f'交叉验证分数: {self.cv_scores}')
                    print(f'平均准确率: {np.mean(scores):.4f} (+/- {np.std(scores) * 2:.4f})')
                except Exception as e:
                    print(f'交叉验证失败: {str(e)}')
                    self.cv_scores = []
            return {'success': True, 'model_path': model_path, 'model_type': self.model_id, 'cv_scores': self.cv_scores if hasattr(self, 'cv_scores') else []}
        except Exception as e:
            print(f'训练过程中发生未预期的错误: {str(e)}')
            return {'success': False, 'error': f'训练过程中发生未预期的错误: {str(e)}'}

    def validation_setup(self, features, estimator):
        """Fit preprocessing within each fold, without seeing its held-out rows."""
        from sklearn.compose import ColumnTransformer
        from sklearn.pipeline import make_pipeline

        raw = self.data.loc[:, features.columns].copy()
        preprocessing = ColumnTransformer(
            [('continuous', StandardScaler(), list(self.scaler.feature_names_in_))],
            remainder='passthrough',
        )
        return raw, make_pipeline(preprocessing, estimator)

    def get_cv_scores(self):
        return self.cv_scores if self.cv_scores is not None else []
if __name__ == '__main__':
    model_id = '1'
    date_range = ['2022-01-01', '2023-01-01']
    valid = 1
    trainer = ModelTrainer(model_id, date_range, valid)
    success = trainer.train()
    print(f"Training status: {('Success' if success['success'] else 'Failed')}")
    if success['success'] and trainer.cv_scores:
        print('Cross-validation scores:', trainer.cv_scores)
        print(f'Mean Accuracy: {np.mean(trainer.cv_scores):.4f} (±{np.std(trainer.cv_scores):.4f})')
