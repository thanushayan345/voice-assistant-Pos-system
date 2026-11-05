import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  Banknote,
  Boxes,
  Award,
} from "lucide-react";
import { api } from "../services/api";
import { useConfig } from "../context/ConfigContext";
import StatCard from "../components/StatCard";
import {
  formatCurrency,
  formatQuantity,
  formatShortDate,
} from "../utils/formatters";

export default function ReportsPage() {
  const { config } = useConfig();
  const sym = config.currency_symbol || "Rs.";

  const [days, setDays] = useState(7);
  const [salesReport, setSalesReport] = useState(null);
  const [invReport, setInvReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [sRep, iRep] = await Promise.all([
        api.getDailySalesReport(days),
        api.getInventoryReport(),
      ]);
      setSalesReport(sRep);
      setInvReport(iRep);
    } catch (err) {
      setError(err.message || "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const dailyPoints = salesReport?.daily_breakdown || [];
  const maxDayAmount = Math.max(
    1,
    ...dailyPoints.map((d) => Number(d.total_amount || 0))
  );

  return (
    <div className="space-y-6 w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <p className="text-sm text-slate-600">
          Daily revenue trends, estimated gross profit, top sellers, and category stock valuation.
        </p>

        <div className="inline-flex rounded-xl bg-white border border-slate-200 p-1 shadow-xs self-start">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                days === d
                  ? "bg-indigo-600 text-white"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Last {d} Days
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-medium">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={`${days}-Day Total Sales`}
          value={
            loading ? "..." : formatCurrency(salesReport?.period_total_sales || 0, sym)
          }
          subtitle={`${salesReport?.period_transactions_count ?? 0} total bills`}
          icon={Banknote}
          tone="emerald"
        />
        <StatCard
          title="Estimated Gross Profit"
          value={
            loading
              ? "..."
              : formatCurrency(salesReport?.estimated_gross_profit || 0, sym)
          }
          subtitle="Selling minus purchase cost"
          icon={TrendingUp}
          tone="indigo"
        />
        <StatCard
          title="Average Bill Value"
          value={
            loading ? "..." : formatCurrency(salesReport?.average_sale_value || 0, sym)
          }
          subtitle={`Over last ${days} days`}
          icon={BarChart3}
          tone="blue"
        />
        <StatCard
          title="Potential Stock Margin"
          value={
            loading
              ? "..."
              : formatCurrency(invReport?.estimated_potential_margin || 0, sym)
          }
          subtitle={`Retail: ${formatCurrency(invReport?.total_retail_value || 0, sym)}`}
          icon={Boxes}
          tone="emerald"
        />
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
        <h3 className="text-base font-bold text-slate-900 mb-4">
          Daily Revenue Breakdown ({sym})
        </h3>
        {loading ? (
          <p className="text-sm text-slate-500 py-8 text-center">Loading chart...</p>
        ) : (
          <div className="grid grid-cols-7 md:flex md:items-end gap-2 h-52 pt-6 border-b border-slate-200 overflow-x-auto pb-2">
            {dailyPoints.map((pt) => {
              const amt = Number(pt.total_amount || 0);
              const pct = Math.max(4, Math.round((amt / maxDayAmount) * 100));
              return (
                <div
                  key={pt.date}
                  className="flex-1 min-w-[44px] flex flex-col items-center justify-end h-full group"
                >
                  <span className="text-[10px] font-bold text-slate-600 mb-1 opacity-85">
                    {amt > 0 ? Math.round(amt).toLocaleString() : "0"}
                  </span>
                  <div
                    style={{ height: `${pct}%` }}
                    title={`${pt.date}: ${formatCurrency(amt, sym)} (${pt.sales_count} bills)`}
                    className={`w-full max-w-[36px] rounded-t-xl transition-all ${
                      amt > 0
                        ? "bg-indigo-500 group-hover:bg-indigo-600"
                        : "bg-slate-200"
                    }`}
                  />
                  <span className="mt-2 text-[11px] font-semibold text-slate-500 whitespace-nowrap">
                    {formatShortDate(pt.date)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-4">
            <Award className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">
              Top Selling Products ({days} Days)
            </h3>
          </div>

          {!salesReport?.top_products?.length ? (
            <p className="text-sm text-slate-500 py-8 text-center">
              No product sales recorded in this period yet.
            </p>
          ) : (
            <div className="divide-y divide-slate-100 text-sm">
              {salesReport.top_products.map((prod, idx) => (
                <div
                  key={prod.product_id}
                  className="py-3 flex items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-800 text-xs font-extrabold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <div>
                      <p className="font-bold text-slate-900">{prod.product_name}</p>
                      <p className="text-xs text-slate-500">
                        Sold: {formatQuantity(prod.total_quantity_sold)} {prod.unit}
                      </p>
                    </div>
                  </div>
                  <span className="font-extrabold text-slate-900">
                    {formatCurrency(prod.total_revenue, sym)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-4">
            <Boxes className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">
              Inventory Valuation by Category
            </h3>
          </div>

          {!invReport?.categories?.length ? (
            <p className="text-sm text-slate-500 py-8 text-center">
              No inventory categories available.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-bold uppercase text-slate-500">
                    <th className="py-2.5">Category</th>
                    <th className="py-2.5 text-center">Items</th>
                    <th className="py-2.5 text-right">Cost Value</th>
                    <th className="py-2.5 text-right">Retail Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {invReport.categories.map((cat) => (
                    <tr key={cat.category}>
                      <td className="py-3 font-bold text-slate-900">{cat.category}</td>
                      <td className="py-3 text-center text-slate-600">
                        {cat.product_count}
                      </td>
                      <td className="py-3 text-right text-slate-600">
                        {formatCurrency(cat.cost_value, sym)}
                      </td>
                      <td className="py-3 text-right font-extrabold text-indigo-700">
                        {formatCurrency(cat.retail_value, sym)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
