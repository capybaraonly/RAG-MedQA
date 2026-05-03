import { TooltipProvider } from '@/components/ui/tooltip';
import { RouterProvider } from 'react-router';
import { routers } from './routes';

export default function App() {
  return (
    <TooltipProvider>
      <RouterProvider router={routers} />
    </TooltipProvider>
  );
}
