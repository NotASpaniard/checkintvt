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
import HistoryPage from "../pages/history";

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
        label="Trang chu"
        icon={<Icon icon="zi-home" />}
        activeIcon={<Icon icon="zi-home" />}
      />
      <BottomNavigation.Item
        key="/history"
        label="Lich su"
        icon={<Icon icon="zi-clock-1" />}
        activeIcon={<Icon icon="zi-clock-1" />}
      />
    </BottomNavigation>
  );
};

const Layout = () => {
  return (
    <App theme={getSystemInfo().zaloTheme}>
      <SnackbarProvider>
        <ZMPRouter>
          <AnimationRoutes>
            <Route path="/" element={<HomePage />} />
            <Route path="/history" element={<HistoryPage />} />
          </AnimationRoutes>
          <CustomBottomNav />
        </ZMPRouter>
      </SnackbarProvider>
    </App>
  );
};
export default Layout;
