
import gc
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy             as np
import pandas            as pd
import seaborn           as sns
from hyperopt                  import fmin, tpe
from scipy.stats               import randint, uniform
from sklearn.base              import BaseEstimator, ClassifierMixin, clone
from sklearn.externals.joblib  import Parallel, delayed, dump
from sklearn.model_selection   import RandomizedSearchCV, ShuffleSplit, cross_val_score
from sklearn.utils.validation  import check_X_y, check_array, check_is_fitted
from sklearn.svm               import SVR
from sklearn.ensemble          import RandomForestRegressor
from xgboost                   import XGBRegressor

class HyperoptSearchCV(BaseEstimator, ClassifierMixin):
    """hyperopt を sklearn で使用するためのラッパークラス
    Parameters
    ----------
    estimator : estimator object
        予測器
    space : dictionary
        ハイパパラメメータの範囲
    n_iter : int
        探索回数
    scoring : string
        評価基準
    cv : int or cross-validation generator
        交差検定の分割数
    n_jobs : int
        並列処理数
    verbose : int
        ログの詳細の度合
    """

    def __init__(
        self,         estimator, space,    n_iter=100,
        scoring=None, cv=None,   n_jobs=1, verbose=0
    ):
        self.estimator = estimator
        self.space     = space
        self.n_iter    = n_iter
        self.scoring   = scoring
        self.cv        = cv
        self.n_jobs    = n_jobs
        self.verbose   = verbose

    def fit(self, X, Y):
        """学習を行うメソッド
        Parameters
        ----------
        X : DataFrame, shape = [n_samples, n_features]
            データ行列
        Y : DataFrame, shpae = [n_samples, n_classes]
            ラベル行列
        Returns
        -------
        self : object
            インスタンス自身
        """

        X, Y                 = check_X_y(X, Y, accept_sparse=True)
        self.X_              = X
        self.Y_              = Y

        # hyperopt を用いてチューニング
        self.best_params_    = fmin(
            self.__objective,
            self.space,
            algo             = tpe.suggest,
            max_evals        = self.n_iter
        )

        # データ全体を用いて再学習
        self.best_estimator_ = self.estimator.set_params(
            **self.best_params_
        ).fit(self.X_, self.Y_)

        del self.X_
        del self.Y_

        gc.collect()

        return self

    def predict(self, X):
        """予測を行うメソッド
        Parameters
        ----------
        X : DataFrame, shape = [n_samples, n_features]
            データ行列
        Returns
        -------
        Y : DataFrame, shpae = [n_samples, n_classes]
            ラベル行列
        """

        check_is_fitted(self, ['best_params_', 'best_estimator_'])

        X = check_array(X, accept_sparse=True)

        return self.best_estimator_.predict(X)

    def __objective(self, kwargs):
        return -cross_val_score(
            clone(self.estimator).set_params(**kwargs),
            self.X_,
            self.y_,
            scoring = self.scoring,
            cv      = self.cv,
            n_jobs  = self.n_jobs,
            verbose = self.verbose
        ).mean()


def plot_variance(X, path):
    """各特徴量の不偏分散を描画する関数
    Parameters
    ----------
    X : DataFrame, shape = [n_samples, n_features]
        データ行列
    path : string
        グラフを保存するパス
    """

    sns.set_style("whitegrid", {'grid.linestyle': ':'})

    # matplotlib のフォントを変更
    plt.rcParams['font.family'] = 'Times New Roman'

    f, ax                       = plt.subplots()
    variances                   = X.var().values
    n_features                  = X.shape[1]
    features                    = np.arange(n_features)

    ax.bar(features, variances, align='center', width=1.0)
    ax.set_xlim(0, n_features)
    ax.set_xlabel('Features')
    ax.set_ylabel('Unbiased variance')
    ax.set_yscale('log')

    # f.set_tight_layout(True)

    # グラフを書込
    f.savefig(path)

    # グラフを消去
    plt.clf


def plot_feature_importance(clf, path):
    """各特徴量の重要度を描画する関数
    Parameters
    ----------
    clf : estimator object
        予測器
    paths : list of string
        各グラフを保存するパス名
    """

    sns.set_style("whitegrid", {'grid.linestyle': ':'})

    # matplotlib のフォントを変更
    plt.rcParams['font.family'] = 'Times New Roman'

    f, ax                   = plt.subplots()
    feature_importances     = clf.feature_importances_
    n_features              = feature_importances.size
    features                = np.arange(n_features)

    ax.bar(features, feature_importances, align='center', width=1.0)
    ax.set_xlim(0, n_features)
    ax.set_ylim(0, 0.02)
    ax.set_xlabel('Features')
    ax.set_ylabel('Feature importance')

    # f.set_tight_layout(True)

    # グラフを書込
    f.savefig(path)

    # グラフを消去
    plt.clf


def main():

    X_train = np.array(pd.read_pickle('./resources/train/data.pkl'))
    Y_train = np.array(pd.read_pickle('./resources/train/target.pkl')).reshape(-1,)

    # 各特徴量の分散を描画
    #plot_variance(X_train, './documents/pictures/variances.png')

    n_samples, n_features = X_train.shape
    n_splits = 5
    random_state = 1

    # 学習したいもののみをリストに追加
    clf_names = ['svm']

    estimator = {
        'svm': SVR(
            epsilon = 0.1,
            kernel = 'rbf',
            degree = 3,
            coef0 = 0,
            shrinking = True,
            tol = 1.0e-03,
            verbose = False,
            max_iter = -1),
        'rf': RandomForestRegressor(
            random_state = random_state,
            n_jobs = -1),
        'xgb' : XGBRegressor(
            seed=random_state)
    }

    param_distributions = {
        'svm':{'C': [1e-04, 1e-03, 1e-02, 1e-01, 1e+00, 1e+01, 1e+02, 1e+03, 1e+04],
               'gamma': [1e-04, 1e-03, 1e-02, 1e-01, 1e+00, 1e+01, 1e+02, 1e+03, 1e+04]},
        'rf': {'max_depth': randint(1, 10),
               'max_features': randint(5, 33),
               'n_estimators': randint(10, 100)},
        'xgb': {'colsample_bylevel': [0.6, 0.7, 0.8, 0.9, 1.0],
                'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
                'gamma': uniform(0.0, 1.0),
                'learning_rate': uniform(0.0, 1.0),
                'max_delta_step': randint(1, 5),
                'max_depth': randint(1, 10),
                'min_child_weight': randint(1, 10),
                'n_estimators': randint(100, 500),
                'subsample': [0.6, 0.7, 0.8, 0.9, 1.0]}}

    for clf_name in clf_names:

        # チューニング
        randomized_search = RandomizedSearchCV(
            estimator = estimator[clf_name],
            param_distributions = param_distributions[clf_name],
            scoring = 'r2',
            cv = ShuffleSplit(
                n_splits = n_splits,
                test_size = 1.0 / n_splits,
                random_state = random_state),
            random_state = random_state,
            n_iter = 81,
            verbose = 1,
            n_jobs = -1).fit(X_train, Y_train)

        best_estimator = randomized_search.best_estimator_
        best_params = randomized_search.best_params_

        if clf_name == 'rf':
            path = './documents/pictures/feature_importances.png'
            # 各特徴量の重要度を描画
            plot_feature_importance(best_estimator, path)

        # 予測器をバイナリデータとして保存
        dump(best_estimator, './resources/estimators/' + clf_name + '.pkl')


if __name__ == '__main__':
    main()