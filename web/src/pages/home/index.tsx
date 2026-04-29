import { Routes } from '@/routes';
import { Navigate } from 'react-router';

const Home = () => {
  return <Navigate to={Routes.Chats} replace />;
};

export default Home;
