import { getSystemInfo } from "zmp-sdk";
import {
  AnimationRoutes,
  App,
  BottomNavigation,
  Route,
  SnackbarProvider,
  ZMPRouter,
  Icon,
} from "zmp-ui";
import { useLocation, useNavigate } from "react-router-dom";

import HomePage from "../pages/index";
// Dung link Railway Cloud
const API_BASE = import.meta.env.VITE_API_BASE || "https://checkintvt-production.up.railway.app";
import HistoryPage from "../pages/history";
import StatsPage from "../pages/stats";
import ProfilePage from "../pages/profile";

const CustomBottomNav = () => {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <BottomNavigation
      fixed
      activeKey={location.pathname}
      onChange={(key) => navigate(key)}
      className="bottom-nav"
    >
      <BottomNavigation.Item
        key="/"
        label="T.Chủ"
        icon={<Icon icon="zi-home" />}
        activeIcon={<Icon icon="zi-home" />}
      />
      <BottomNavigation.Item
        key="/history"
        label="Lịch sử"
        icon={<Icon icon="zi-clock-1" />}
        activeIcon={<Icon icon="zi-clock-1" />}
      />
      <BottomNavigation.Item
        key="/stats"
        label="Thống kê"
        icon={<Icon icon="zi-poll" />}
        activeIcon={<Icon icon="zi-poll" />}
      />
      <BottomNavigation.Item
        key="/profile"
        label="Cá nhân"
        icon={<Icon icon="zi-user" />}
        activeIcon={<Icon icon="zi-user" />}
      />
    </BottomNavigation >
  );
};

const Layout = () => {
  const systemInfo = getSystemInfo() || {};
  return (
    <App theme={systemInfo.zaloTheme || "light"}>
      <SnackbarProvider>
        <ZMPRouter>
          <AnimationRoutes>
            <Route path="/" element={<HomePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </AnimationRoutes>
          <CustomBottomNav />
        </ZMPRouter>
      </SnackbarProvider>
    </App>
  );
};
export default Layout;
