import { RouterProvider } from 'react-router';
import { routers } from './routes';

export default function App() {
  return <RouterProvider router={routers} />;
}
