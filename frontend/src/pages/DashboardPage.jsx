import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Banknote,
  Package,
  Boxes,
  AlertTriangle,
  Receipt,
  Search,
  Mic,
  ArrowRight,
  RefreshCw,
  ShoppingCart,
} from "lucide-react";
import { api } from "../services/api";
import { useConfig } from "../context/ConfigContext";
import StatCard from "../components/StatCard";
import StockBadge from "../components/StockBadge";
import ReceiptModal from "../components/ReceiptModal";
import {
  formatCurrency,
  formatDateTime,
  formatQuantity,
} from "../utils/formatters";

export default function DashboardPage() {
  const { config } = useConfig();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [quickSearch, setQuickSearch] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedSale, setSelectedSale] = useState(null);

  const sym = report?.currency_symbol || config.currency_symbol || "Rs.";

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getDashboardReport();
      setReport(data);
    } catch (err) {
      setError(err.message || "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    const trimmed = quickSearch.trim();
    if (!trimmed) {
      setSearchResults([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const items = await api.getProducts({ search: trimmed });
        setSearchResults(items.slice(0, 6));
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 220);
    return () => clearTimeout(timer);
  }, [quickSearch]);

  return (
    <div className="space-y-6 w-full">
      {/* Modern Hero Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-indigo-900 p-6 text-white shadow-md flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div>
          <span className="inline-block px-3 py-1 rounded-full bg-indigo-500/25 text-indigo-200 text-xs font-bold tracking-wide uppercase mb-2">
            Live Store Overview
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold">
            Smart Point of Sale & Inventory
          </h2>
          <p className="mt-1 text-slate-300 text-sm max-w-xl">
            Manage billing, track stock valuation in real time, and execute inventory updates by voice with safe confirmation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => navigate("/voice")}
            className="inline-flex items-center gap-2.5 px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm shadow-md transition"
          >
            <Mic className="w-4 h-4" />
            Voice Assistant
          </button>
          <button
            type="button"
            onClick={() => navigate("/pos")}
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white border border-white/15 font-bold text-sm transition"
          >
            <ShoppingCart className="w-4 h-4" />
            Open POS Terminal
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm font-medium flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchDashboard}
            className="px-3 py-1.5 rounded-xl bg-rose-100 hover:bg-rose-200 text-xs font-bold"
          >
            Retry
          </button>
        </div>
      )}

      {/* Dynamic KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <StatCard
          title={`Today's Sales (${config.currency})`}
          value={loading ? "..." : formatCurrency(report?.today_total_sales || 0, sym)}
          subtitle="Live daily revenue"
          icon={Banknote}
          tone="emerald"
        />
        <StatCard
          title="Today's Transactions"
          value={loading ? "..." : String(report?.today_transactions_count ?? 0)}
          subtitle="Completed bills today"
          icon={Receipt}
          tone="indigo"
        />
        <StatCard
          title="Total Products"
          value={loading ? "..." : String(report?.total_products ?? 0)}
          subtitle="Active catalog items"
          icon={Package}
          tone="blue"
        />
        <StatCard
          title={`Total Stock Value (${config.currency})`}
          value={loading ? "..." : formatCurrency(report?.total_stock_value || 0, sym)}
          subtitle={`Cost: ${formatCurrency(report?.total_stock_cost_value || 0, sym)}`}
          icon={Boxes}
          tone="emerald"
        />
        <StatCard
          title="Low-Stock Alerts"
          value={loading ? "..." : String(report?.low_stock_count ?? 0)}
          subtitle="Items needing restock"
          icon={AlertTriangle}
          tone={(report?.low_stock_count || 0) > 0 ? "amber" : "emerald"}
        />
      </div>

      {/* Quick Product Search Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-slate-900">
            Quick Product Lookup
          </h3>
          <button
            type="button"
            onClick={fetchDashboard}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-indigo-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        <div className="relative">
          <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={quickSearch}
            onChange={(e) => setQuickSearch(e.target.value)}
            placeholder="Search products by name, category, or barcode (e.g., Rice, Sugar, Milk, Tea, Soap)..."
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {quickSearch.trim() && (
          <div className="mt-3 divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
            {searching ? (
              <p className="p-4 text-xs text-slate-500">Searching catalog...</p>
            ) : searchResults.length === 0 ? (
              <p className="p-4 text-xs text-slate-500">
                No matching products found for &ldquo;{quickSearch}&rdquo;.
              </p>
            ) : (
              searchResults.map((prod) => (
                <div
                  key={prod.product_id}
                  className="p-3.5 bg-slate-50/60 hover:bg-slate-100/80 flex flex-wrap items-center justify-between gap-3"
                >
                  <div>
                    <p className="text-sm font-bold text-slate-900">
                      {prod.product_name}
                    </p>
                    <p className="text-xs text-slate-500">
                      Category: {prod.category} • Price:{" "}
                      <strong className="text-slate-800">
                        {formatCurrency(prod.selling_price, sym)} / {prod.unit}
                      </strong>
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-slate-800">
                      {formatQuantity(prod.stock_quantity)} {prod.unit}
                    </span>
                    <StockBadge
                      stockQuantity={prod.stock_quantity}
                      lowStockLimit={prod.low_stock_limit}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Low Stock Alerts & Recent Sales Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              <h3 className="text-base font-bold text-slate-900">Low-Stock Alerts</h3>
            </div>
            <Link
              to="/inventory"
              className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 hover:underline"
            >
              Manage Stock <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {!report?.low_stock_products?.length ? (
            <div className="flex-1 flex flex-col items-center justify-center py-8 text-center">
              <p className="text-sm font-semibold text-emerald-700">
                All products are well stocked!
              </p>
              <p className="text-xs text-slate-500 mt-1">
                No items are below their low-stock threshold.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {report.low_stock_products.map((item) => (
                <div
                  key={item.product_id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-amber-50/70 border border-amber-200/80"
                >
                  <div>
                    <p className="text-sm font-bold text-slate-900">
                      {item.product_name}
                    </p>
                    <p className="text-xs text-amber-800">
                      Threshold: {formatQuantity(item.low_stock_limit)} {item.unit}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-extrabold text-rose-700">
                      {formatQuantity(item.stock_quantity)} {item.unit}
                    </p>
                    <Link
                      to="/inventory"
                      className="text-[11px] font-bold text-indigo-700 hover:underline"
                    >
                      + Restock
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Receipt className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-900">Recent Sales</h3>
            </div>
            <Link
              to="/sales"
              className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 hover:underline"
            >
              Full History <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {!report?.recent_sales?.length ? (
            <div className="flex-1 flex flex-col items-center justify-center py-8 text-center">
              <p className="text-sm font-semibold text-slate-600">
                No sales recorded yet today.
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Create a bill in POS or record a sale using Voice Assistant.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {report.recent_sales.map((sale) => (
                <div
                  key={sale.id}
                  className="py-3 flex items-center justify-between gap-3"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">
                        {sale.invoice_number}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          sale.source === "VOICE"
                            ? "bg-purple-100 text-purple-800"
                            : "bg-sky-100 text-sky-800"
                        }`}
                      >
                        {sale.source}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">
                      {formatDateTime(sale.created_at)} • {sale.items?.length || 0} item(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-extrabold text-slate-900">
                      {formatCurrency(sale.total_amount, sym)}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedSale(sale)}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      Receipt
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ReceiptModal sale={selectedSale} onClose={() => setSelectedSale(null)} />
    </div>
  );
}
