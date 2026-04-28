import { memo, Suspense, lazy } from 'react';
import {
  createBrowserRouter,
  Navigate,
  redirect,
  type RouteObject,
} from 'react-router';
import FallbackComponent from './components/fallback-component';
import authorizationUtil from './utils/authorization-util';

export enum Routes {
  Root = '/',
  Login = '/login-next',
  Logout = '/logout',
  Home = '/home',
  Datasets = '/datasets',
  DatasetBase = '/dataset',
  Dataset = `${Routes.DatasetBase}${Routes.DatasetBase}`,
  Searches = '/searches',
  Search = '/search',
  SearchShare = '/search/share',
  Chats = '/chats',
  Chat = '/chat',
  Files = '/files',
  ProfileSetting = '/profile-setting',
  Profile = '/profile',
  Api = '/api',
  Mcp = '/mcp',
  Team = '/team',
  Plan = '/plan',
  Model = '/model',
  Prompt = '/prompt',
  DataSource = '/data-source',
  DataSourceDetailPage = '/data-source-detail-page',
  DatasetTesting = '/testing',
  Chunk = '/chunk',
  ChunkResult = `${Chunk}${Chunk}`,
  Parsed = '/parsed',
  ParsedResult = `${Chunk}${Parsed}`,
  Result = '/result',
  ResultView = `${Chunk}${Result}`,
  KnowledgeGraph = '/knowledge-graph',
  ChatShare = `${Chats}/share`,
  ChatWidget = `${Chats}/widget`,
  UserSetting = '/user-setting',
  DataSetOverview = '/dataset-overview',
  DataSetSetting = '/dataset-setting',
}

const defaultRouteFallback = (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[1px]">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/70 border-t-transparent" />
  </div>
);

type LazyRouteConfig = Omit<RouteObject, 'Component' | 'children'> & {
  Component?: () => Promise<{ default: React.ComponentType<any> }>;
  children?: LazyRouteConfig[];
};

const withLazyRoute = (
  importer: () => Promise<{ default: React.ComponentType<any> }>,
  fallback: React.ReactNode = defaultRouteFallback,
) => {
  const LazyComponent = lazy(importer);
  const Wrapped: React.FC<any> = (props) => (
    <Suspense fallback={fallback}>
      <LazyComponent {...props} />
    </Suspense>
  );
  Wrapped.displayName = `LazyRoute(${
    (LazyComponent as unknown as React.ComponentType<any>).displayName ||
    LazyComponent.name ||
    'Component'
  })`;
  return process.env.NODE_ENV === 'development' ? LazyComponent : memo(Wrapped);
};

const routeConfigOptions = [
  {
    path: '/login',
    Component: () => import('@/pages/login-next'),
    layout: false,
  },
  {
    path: '/login-next',
    Component: () => import('@/pages/login-next'),
    layout: false,
  },
  {
    path: Routes.ChatShare,
    Component: () => import('@/pages/next-chats/share'),
    layout: false,
  },
  {
    path: Routes.ChatWidget,
    Component: () => import('@/pages/next-chats/widget'),
    layout: false,
  },
  {
    path: '/document/:id',
    Component: () => import('@/pages/document-viewer'),
    layout: false,
  },
  {
    path: '/*',
    Component: () => import('@/pages/404'),
    layout: false,
  },
  {
    path: Routes.Root,
    layout: false,
    Component: () => import('@/layouts/root-layout'),
    loader: ({ request }: { request: Request }) => {
      const url = new URL(request.url);
      const auth = url.searchParams.get('auth');
      if (auth) {
        authorizationUtil.setAuthorization(auth);
        url.searchParams.delete('auth');
        return redirect(`${url.pathname}${url.search}`);
      }
      return null;
    },
    children: [
      {
        path: Routes.Root,
        Component: () => import('@/pages/home'),
      },
    ],
  },
  {
    path: Routes.Chat + '/:id',
    Component: () => import('@/pages/next-chats/chat'),
  },
  {
    path: Routes.Root,
    Component: () => import('@/layouts/root-layout'),
    children: [
      {
        path: Routes.Datasets,
        Component: () => import('@/pages/datasets'),
      },
      {
        path: Routes.DatasetBase,
        Component: () => import('@/pages/dataset'),
        children: [
          {
            path: `${Routes.Dataset}/:id`,
            Component: () => import('@/pages/dataset/dataset'),
          },
          {
            path: `${Routes.DatasetBase}${Routes.DatasetTesting}/:id`,
            Component: () => import('@/pages/dataset/testing'),
          },
          {
            path: `${Routes.DatasetBase}${Routes.KnowledgeGraph}/:id`,
            Component: () => import('@/pages/dataset/knowledge-graph'),
          },
          {
            path: `${Routes.DatasetBase}${Routes.DataSetOverview}/:id`,
            Component: () => import('@/pages/dataset/dataset-overview'),
          },
          {
            path: `${Routes.DatasetBase}${Routes.DataSetSetting}/:id`,
            Component: () => import('@/pages/dataset/dataset-setting'),
          },
        ],
      },
      {
        path: Routes.Chats,
        Component: () => import('@/pages/next-chats'),
      },
      {
        path: Routes.Searches,
        Component: () => import('@/pages/next-searches'),
      },
      {
        path: `${Routes.Search}/:id`,
        layout: false,
        Component: () => import('@/pages/next-search'),
      },
      {
        path: Routes.Files,
        Component: () => import('@/pages/files'),
      },
      {
        path: Routes.UserSetting,
        Component: () => import('@/pages/user-setting'),
        layout: false,
        children: [
          {
            path: Routes.UserSetting,
            element: (
              <Navigate to={`/user-setting${Routes.DataSource}`} replace />
            ),
          },
          {
            path: `${Routes.UserSetting}/profile`,
            Component: () => import('@/pages/user-setting/profile'),
          },
          {
            path: `${Routes.UserSetting}/model`,
            Component: () => import('@/pages/user-setting/setting-model'),
          },
          {
            path: `${Routes.UserSetting}/team`,
            Component: () => import('@/pages/user-setting/setting-team'),
          },
          {
            path: `${Routes.UserSetting}${Routes.Api}`,
            Component: () => import('@/pages/user-setting/setting-api'),
          },
          {
            path: `${Routes.UserSetting}${Routes.Mcp}`,
            Component: () => import('@/pages/user-setting/mcp'),
          },
          {
            path: `${Routes.UserSetting}${Routes.DataSource}`,
            Component: () => import('@/pages/user-setting/data-source'),
          },
        ],
      },
      {
        path: `${Routes.UserSetting}${Routes.DataSource}${Routes.DataSourceDetailPage}`,
        layout: false,
        Component: () =>
          import('@/pages/user-setting/data-source/data-source-detail-page'),
      },
    ],
  },
  {
    path: `${Routes.SearchShare}`,
    Component: () => import('@/pages/next-search/share'),
  },
  {
    path: Routes.Chunk,
    children: [
      {
        path: `${Routes.Chunk}`,
        Component: () => import('@/pages/chunk'),
      },
      {
        path: `${Routes.ParsedResult}/chunks`,
        Component: () =>
          import('@/pages/chunk/parsed-result/add-knowledge/components/knowledge-chunk'),
      },
      {
        path: `${Routes.ChunkResult}/:id`,
        Component: () => import('@/pages/chunk/chunk-result'),
      },
      {
        path: `${Routes.ResultView}/:id`,
        Component: () => import('@/pages/chunk/result-view'),
      },
    ],
  },
];

const wrapRoutes = (routes: LazyRouteConfig[]): RouteObject[] =>
  routes.map((item) => {
    const { Component, children, ...rest } = item;
    const next: RouteObject = { ...rest, errorElement: <FallbackComponent /> };
    if (Component) {
      next.Component = withLazyRoute(Component);
    }
    if (children) {
      next.children = wrapRoutes(children);
    }
    return next;
  });

const routeConfig = wrapRoutes(routeConfigOptions);

const routers = createBrowserRouter(routeConfig, {
  basename: import.meta.env.VITE_BASE_URL || '/',
});

export { routers };
