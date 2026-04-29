import { lazy, memo, Suspense } from 'react';
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
  Chats = '/chats',
  Chat = '/chat',
  UserSetting = '/user-setting',
  Profile = '/profile',
  Model = '/model',
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

const routeConfigOptions: LazyRouteConfig[] = [
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
        element: <Navigate to={Routes.Chats} replace />,
      },
      {
        path: Routes.Chats,
        Component: () => import('@/pages/next-chats'),
      },
      {
        path: `${Routes.Chat}/:id`,
        Component: () => import('@/pages/next-chats/chat'),
        layout: false,
      },
    ],
  },
  {
    path: Routes.UserSetting,
    Component: () => import('@/pages/user-setting'),
    layout: false,
    children: [
      {
        path: `${Routes.UserSetting}/profile`,
        Component: () => import('@/pages/user-setting/profile'),
      },
      {
        path: `${Routes.UserSetting}/model`,
        Component: () => import('@/pages/user-setting/setting-model'),
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
