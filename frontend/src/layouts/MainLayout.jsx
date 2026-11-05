import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Boxes,
  History,
  BarChart3,
  Mic,
  Settings,
  LogOut,
  Menu,
  X,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useSystemStatus } from "../hooks/useSystemStatus";
import MaintenanceBanner from "../components/MaintenanceBanner";

const BASE_NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/pos", label: "POS / Billing", icon: ShoppingCart, featureKey: "posBilling" },
  { to: "/products", label: "Products", icon: Package, featureKey: "productManagement" },
  { to: "/inventory", label: "Inventory", icon: Boxes, featureKey: "inventoryAdjustments" },
  { to: "/sales", label: "Sales History", icon: History },
  { to: "/reports", label: "Reports", icon: BarChart3, featureKey: "reportsAnalytics" },
  {
    to: "/voice",
    label: "Voice Assistant",
    icon: Mic,
    highlight: true,
    featureKey: "voiceAssistant",
  },
  { to: "/settings", label: "Settings", icon: Settings },
];

const MOBILE_BOTTOM_TABS = [
  { to: "/", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/pos", label: "POS", icon: ShoppingCart },
  { to: "/voice", label: "Voice AI", icon: Mic, center: true },
  { to: "/products", label: "Products", icon: Package },
  { to: "/inventory", label: "Stock", icon: Boxes },
];

export default function MainLayout() {
  const { user, logout } = useAuth();
  const { config, ttsEnabled, setTtsEnabled } = useConfig();
  const { features } = useSystemStatus();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const navigate = useNavigate();
  const location = useLocation();

  const isAdmin = ["owner", "admin"].includes((user?.role || "").toLowerCase());
  const navItems = isAdmin
    ? [
        ...BASE_NAV_ITEMS,
        { to: "/admin", label: "Admin Controls", icon: ShieldAlert },
      ]
    : BASE_NAV_ITEMS;

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch {
      // Ignore if browser blocks fullscreen API
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const activeNav =
    navItems.find((item) =>
      item.end ? location.pathname === "/" : location.pathname.startsWith(item.to)
    ) || navItems[0];

  return (
    <div className="h-screen w-full overflow-hidden bg-slate-100 flex flex-col lg:flex-row">
      {/* Desktop Non-Overlapping Flex Sidebar */}
      <aside
        className={`hidden lg:flex lg:flex-col shrink-0 bg-slate-900 text-slate-200 border-r border-slate-800 transition-all duration-200 ${
          sidebarCollapsed ? "lg:w-20" : "lg:w-64"
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shrink-0">
              <Mic className="w-5 h-5" />
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <h1 className="text-base font-extrabold text-white truncate">
                  Voice POS
                </h1>
                <p className="text-[11px] font-medium text-slate-400 truncate">
                  Smart Retail System
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const featureOff =
              item.featureKey && features && features[item.featureKey] === false;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={sidebarCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center ${
                    sidebarCollapsed
                      ? "justify-center px-2"
                      : "justify-between px-3.5 gap-3"
                  } py-2.5 rounded-xl text-sm font-semibold transition ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm"
                      : item.highlight
                      ? "bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25 hover:text-white"
                      : "text-slate-400 hover:bg-slate-800 hover:text-white"
                  }`
                }
              >
                <span className="flex items-center gap-3 min-w-0">
                  <Icon className="w-5 h-5 shrink-0" />
                  {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
                </span>
                {!sidebarCollapsed && featureOff && (
                  <span className="px-1.5 py-0.5 rounded bg-rose-500/25 text-rose-200 text-[10px] font-extrabold shrink-0">
                    OFF
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/50 space-y-2.5 shrink-0">
          {!sidebarCollapsed && (
            <div className="flex items-center justify-between px-1 text-xs">
              <span className="text-slate-400 font-medium truncate">
                Ollama ({config.ollama_model || "qwen2.5:3b"})
              </span>
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full font-semibold shrink-0 ${
                  config.ai_configured
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-amber-500/20 text-amber-300"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    config.ai_configured ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
                {config.ai_configured
                  ? "Local Ready"
                  : config.ollama_connected
                  ? "Pull Model"
                  : "Offline"}
              </span>
            </div>
          )}

          <div
            className={`flex items-center ${
              sidebarCollapsed ? "justify-center" : "justify-between px-1"
            } pt-2 border-t border-slate-800`}
          >
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">
                  {user?.full_name || user?.username}
                </p>
                <p className="text-[11px] text-slate-400 capitalize truncate">
                  {user?.role || "owner"} • {config.currency}
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={handleLogout}
              title="Sign Out"
              className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Full-Width Content Shell */}
      <div className="flex-1 min-w-0 flex flex-col h-full overflow-hidden">
        {/* Top Bar */}
        <header className="h-16 shrink-0 bg-white border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between gap-3 z-20">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Drawer Trigger */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-100"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Desktop Sidebar Collapse/Expand Trigger */}
            <button
              type="button"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden lg:inline-flex p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="w-4 h-4" />
              ) : (
                <PanelLeftClose className="w-4 h-4" />
              )}
            </button>

            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-extrabold text-slate-900 truncate">
                {activeNav.label}
              </h2>
            </div>

            <span className="hidden md:inline-flex items-center px-2.5 py-1 rounded-lg bg-slate-100 text-xs font-bold text-slate-700 border border-slate-200">
              {config.currency} ({config.currency_symbol})
            </span>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
            {/* TTS Mute/Unmute */}
            <button
              type="button"
              onClick={() => setTtsEnabled(!ttsEnabled)}
              title={ttsEnabled ? "Voice audio enabled" : "Voice audio muted"}
              className={`p-2 rounded-xl border transition ${
                ttsEnabled
                  ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                  : "border-slate-200 bg-white text-slate-400"
              }`}
            >
              {ttsEnabled ? (
                <Volume2 className="w-4 h-4" />
              ) : (
                <VolumeX className="w-4 h-4" />
              )}
            </button>

            {/* Dedicated Fullscreen Toggle Button */}
            <button
              type="button"
              onClick={toggleFullscreen}
              title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-bold text-slate-700 transition"
            >
              {isFullscreen ? (
                <>
                  <Minimize2 className="w-4 h-4" />
                  <span className="hidden sm:inline">Exit Fullscreen</span>
                </>
              ) : (
                <>
                  <Maximize2 className="w-4 h-4" />
                  <span className="hidden sm:inline">Fullscreen</span>
                </>
              )}
            </button>

            {location.pathname !== "/voice" && (
              <button
                type="button"
                onClick={() => navigate("/voice")}
                className="hidden sm:inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition"
              >
                <Mic className="w-4 h-4" />
                <span>Voice AI</span>
              </button>
            )}
          </div>
        </header>

        {/* Mobile Slide-Over Menu */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 lg:hidden flex">
            <div
              className="fixed inset-0 bg-slate-900/60"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="relative w-72 max-w-[82vw] bg-slate-900 text-white h-full shadow-2xl flex flex-col z-10">
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                    <Mic className="w-4 h-4 text-white" />
                  </div>
                  <span className="font-extrabold text-white">Voice POS</span>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const featureOff =
                    item.featureKey && features && features[item.featureKey] === false;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center justify-between gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold ${
                          isActive
                            ? "bg-indigo-600 text-white"
                            : "text-slate-300 hover:bg-slate-800"
                        }`
                      }
                    >
                      <span className="flex items-center gap-3 min-w-0">
                        <Icon className="w-5 h-5 shrink-0" />
                        <span className="truncate">{item.label}</span>
                      </span>
                      {featureOff && (
                        <span className="px-1.5 py-0.5 rounded bg-rose-500/25 text-rose-200 text-[10px] font-extrabold shrink-0">
                          OFF
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </nav>
              <div className="p-4 border-t border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-white">{user?.full_name}</p>
                  <p className="text-xs text-slate-400">@{user?.username}</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/20 text-rose-300 text-xs font-bold"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Real-Time System Maintenance Banner (No Page Refresh Required) */}
        <MaintenanceBanner />

        {/* Scrollable Full-Screen Page Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 pb-24 lg:pb-6 w-full">
          <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-slate-200 px-2 py-1.5 grid grid-cols-5 items-center shadow-lg">
        {MOBILE_BOTTOM_TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center py-1 rounded-xl text-[11px] font-semibold transition ${
                  tab.center
                    ? isActive
                      ? "text-white bg-indigo-600 shadow-md -mt-4 py-2.5 mx-1 rounded-2xl"
                      : "text-indigo-700 bg-indigo-50 -mt-4 py-2.5 mx-1 rounded-2xl border border-indigo-200"
                    : isActive
                    ? "text-indigo-700"
                    : "text-slate-500"
                }`
              }
            >
              <Icon className="w-5 h-5 mb-0.5" />
              <span>{tab.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
