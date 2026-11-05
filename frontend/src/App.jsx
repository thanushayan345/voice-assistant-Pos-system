import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "./context/ConfigContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SystemStatusProvider, useSystemStatus } from "./hooks/useSystemStatus";
import MainLayout from "./layouts/MainLayout";
import MaintenanceScreen from "./components/MaintenanceScreen";
import FeatureGate from "./components/FeatureGate";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PosPage from "./pages/PosPage";
import ProductsPage from "./pages/ProductsPage";
import InventoryPage from "./pages/InventoryPage";
import SalesHistoryPage from "./pages/SalesHistoryPage";
import ReportsPage from "./pages/ReportsPage";
import VoiceAssistantPage from "./pages/VoiceAssistantPage";
import SettingsPage from "./pages/SettingsPage";
import AdminControlPage from "./pages/AdminControlPage";

function ProtectedRoute({ children }) {
  const { isAuthenticated, loadingAuth, user } = useAuth();
  const { maintenance, blocking, adminPreviewBlocking } = useSystemStatus();

  if (loadingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 text-sm font-semibold text-slate-600">
        Loading Voice POS...
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const isAdmin = ["owner", "admin"].includes((user?.role || "").toLowerCase());
  if (maintenance && blocking && (!isAdmin || adminPreviewBlocking)) {
    return <MaintenanceScreen />;
  }

  return children;
}

function PublicOnlyRoute({ children }) {
  const { isAuthenticated, loadingAuth } = useAuth();
  if (loadingAuth) return null;
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  return children;
}

export default function App() {
  return (
    <ConfigProvider>
      <AuthProvider>
        <SystemStatusProvider>
          <BrowserRouter>
            <Routes>
              <Route
                path="/login"
                element={
                  <PublicOnlyRoute>
                    <LoginPage />
                  </PublicOnlyRoute>
                }
              />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <MainLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<DashboardPage />} />
                <Route
                  path="pos"
                  element={
                    <FeatureGate featureKey="posBilling" featureLabel="POS & Billing">
                      <PosPage />
                    </FeatureGate>
                  }
                />
                <Route
                  path="products"
                  element={
                    <FeatureGate
                      featureKey="productManagement"
                      featureLabel="Product Management"
                    >
                      <ProductsPage />
                    </FeatureGate>
                  }
                />
                <Route
                  path="inventory"
                  element={
                    <FeatureGate
                      featureKey="inventoryAdjustments"
                      featureLabel="Inventory Management"
                    >
                      <InventoryPage />
                    </FeatureGate>
                  }
                />
                <Route path="sales" element={<SalesHistoryPage />} />
                <Route
                  path="reports"
                  element={
                    <FeatureGate
                      featureKey="reportsAnalytics"
                      featureLabel="Reports & Analytics"
                    >
                      <ReportsPage />
                    </FeatureGate>
                  }
                />
                <Route
                  path="voice"
                  element={
                    <FeatureGate
                      featureKey="voiceAssistant"
                      featureLabel="Voice Assistant"
                    >
                      <VoiceAssistantPage />
                    </FeatureGate>
                  }
                />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="admin" element={<AdminControlPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SystemStatusProvider>
      </AuthProvider>
    </ConfigProvider>
  );
}
