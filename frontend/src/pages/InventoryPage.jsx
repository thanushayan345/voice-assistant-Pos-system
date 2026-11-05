import React, { useCallback, useEffect, useState } from "react";
import {
  Boxes,
  AlertTriangle,
  ArrowUpCircle,
  ArrowDownCircle,
  History,
  X,
} from "lucide-react";
import { api } from "../services/api";
import { useConfig } from "../context/ConfigContext";
import StockBadge from "../components/StockBadge";
import ConfirmModal from "../components/ConfirmModal";
import {
  formatCurrency,
  formatDateTime,
  formatQuantity,
} from "../utils/formatters";

export default function InventoryPage() {
  const { config } = useConfig();
  const sym = config.currency_symbol || "Rs.";

  const [tab, setTab] = useState("all");
  const [overview, setOverview] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [adjustModal, setAdjustModal] = useState(null);
  const [adjQty, setAdjQty] = useState("");
  const [adjReason, setAdjReason] = useState("");
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [invData, txList] = await Promise.all([
        api.getInventory(),
        api.getStockTransactions({ limit: 100 }),
      ]);
      setOverview(invData);
      setTransactions(txList);
    } catch (err) {
      setError(err.message || "Could not load inventory data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openAdjust = (product, type) => {
    setAdjustModal({ product, type });
    setAdjQty("");
    setAdjReason("");
    setPendingConfirm(false);
    setError("");
  };

  const handleRequestAdjust = (e) => {
    e.preventDefault();
    const num = Number(adjQty);
    if (!num || num <= 0) {
      setError("Please enter a valid quantity greater than zero.");
      return;
    }
    if (
      adjustModal.type === "REDUCE" &&
      num > Number(adjustModal.product.stock_quantity)
    ) {
      setError(
        `Insufficient stock! Available: ${formatQuantity(
          adjustModal.product.stock_quantity
        )} ${adjustModal.product.unit}.`
      );
      return;
    }
    setPendingConfirm(true);
  };

  const executeConfirmedAdjustment = async () => {
    if (!adjustModal) return;
    setSubmitting(true);
    setError("");
    try {
      await api.adjustInventory({
        product_id: adjustModal.product.product_id,
        adjustment_type: adjustModal.type,
        quantity: Number(adjQty),
        reason:
          adjReason.trim() ||
          `Manual ${adjustModal.type.toLowerCase()} via Inventory Dashboard`,
      });
      setPendingConfirm(false);
      setAdjustModal(null);
      await loadData();
    } catch (err) {
      setError(err.message || "Stock adjustment failed.");
      setPendingConfirm(false);
    } finally {
      setSubmitting(false);
    }
  };

  const items = overview?.items || [];
  const displayedItems =
    tab === "low" ? items.filter((i) => i.is_low_stock) : items;

  return (
    <div className="space-y-5 w-full">
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-medium">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <span className="text-xs font-bold uppercase text-slate-500">
            Total SKUs
          </span>
          <p className="text-2xl font-extrabold text-slate-900 mt-1">
            {overview?.total_products ?? 0}
          </p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <span className="text-xs font-bold uppercase text-amber-600">
            Low Stock Items
          </span>
          <p className="text-2xl font-extrabold text-amber-700 mt-1">
            {overview?.low_stock_count ?? 0}
          </p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <span className="text-xs font-bold uppercase text-slate-500">
            Retail Stock Value
          </span>
          <p className="text-2xl font-extrabold text-indigo-700 mt-1">
            {formatCurrency(overview?.total_retail_value || 0, sym)}
          </p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-4">
          <span className="text-xs font-bold uppercase text-slate-500">
            Purchase Cost Value
          </span>
          <p className="text-2xl font-extrabold text-slate-800 mt-1">
            {formatCurrency(overview?.total_cost_value || 0, sym)}
          </p>
        </div>
      </div>

      <div className="inline-flex rounded-2xl bg-white border border-slate-200 p-1 shadow-xs">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition ${
            tab === "all"
              ? "bg-indigo-600 text-white"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Boxes className="w-4 h-4" />
          All Stock ({items.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("low")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition ${
            tab === "low"
              ? "bg-amber-600 text-white"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          Low Stock ({overview?.low_stock_count ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setTab("ledger")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition ${
            tab === "ledger"
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <History className="w-4 h-4" />
          Transactions Ledger
        </button>
      </div>

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-sm text-slate-500">
          Loading inventory...
        </div>
      ) : tab === "ledger" ? (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase text-slate-500">
                  <th className="py-3.5 px-4">Date & Time</th>
                  <th className="py-3.5 px-4">Product</th>
                  <th className="py-3.5 px-4">Type</th>
                  <th className="py-3.5 px-4 text-right">Qty</th>
                  <th className="py-3.5 px-4 text-right">Stock Change</th>
                  <th className="py-3.5 px-4">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/70">
                    <td className="py-3 px-4 text-xs text-slate-500 whitespace-nowrap">
                      {formatDateTime(tx.created_at)}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      {tx.product_name}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          tx.transaction_type === "ADD" ||
                          tx.transaction_type === "INITIAL"
                            ? "bg-emerald-100 text-emerald-800"
                            : tx.transaction_type === "SALE"
                            ? "bg-sky-100 text-sky-800"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {tx.transaction_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      {formatQuantity(tx.quantity)} {tx.unit}
                    </td>
                    <td className="py-3 px-4 text-right text-xs font-mono text-slate-600">
                      {formatQuantity(tx.previous_stock)} →{" "}
                      <strong className="text-slate-900">
                        {formatQuantity(tx.new_stock)}
                      </strong>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {tx.reason || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          {displayedItems.length === 0 ? (
            <div className="p-10 text-center text-sm text-slate-500">
              No items in this view.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase text-slate-500">
                    <th className="py-3.5 px-4">Product</th>
                    <th className="py-3.5 px-4">Category</th>
                    <th className="py-3.5 px-4 text-right">Current Stock</th>
                    <th className="py-3.5 px-4 text-right">Low Limit</th>
                    <th className="py-3.5 px-4 text-right">Stock Value</th>
                    <th className="py-3.5 px-4 text-center">Status</th>
                    <th className="py-3.5 px-4 text-right">Quick Adjust</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {displayedItems.map((item) => (
                    <tr key={item.product_id} className="hover:bg-slate-50/70">
                      <td className="py-3.5 px-4 font-bold text-slate-900">
                        {item.product_name}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">{item.category}</td>
                      <td className="py-3.5 px-4 text-right font-extrabold text-slate-900">
                        {formatQuantity(item.stock_quantity)}{" "}
                        <span className="text-xs font-normal text-slate-500">
                          {item.unit}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right text-slate-500">
                        {formatQuantity(item.low_stock_limit)} {item.unit}
                      </td>
                      <td className="py-3.5 px-4 text-right font-semibold text-slate-800">
                        {formatCurrency(item.stock_retail_value, sym)}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <StockBadge
                          stockQuantity={item.stock_quantity}
                          lowStockLimit={item.low_stock_limit}
                        />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => openAdjust(item, "ADD")}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200"
                          >
                            <ArrowUpCircle className="w-3.5 h-3.5" />
                            Add
                          </button>
                          <button
                            type="button"
                            onClick={() => openAdjust(item, "REDUCE")}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-bold border border-amber-200"
                          >
                            <ArrowDownCircle className="w-3.5 h-3.5" />
                            Reduce
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {adjustModal && !pendingConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h3 className="text-lg font-extrabold text-slate-900">
                {adjustModal.type === "ADD" ? "Add Stock" : "Reduce Stock"} •{" "}
                {adjustModal.product.product_name}
              </h3>
              <button
                type="button"
                onClick={() => setAdjustModal(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRequestAdjust} className="p-6 space-y-4">
              <p className="text-xs text-slate-600">
                Current Stock:{" "}
                <strong className="text-slate-900">
                  {formatQuantity(adjustModal.product.stock_quantity)}{" "}
                  {adjustModal.product.unit}
                </strong>
              </p>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Quantity ({adjustModal.product.unit}) *
                </label>
                <input
                  type="number"
                  min="0.001"
                  step="any"
                  required
                  value={adjQty}
                  onChange={(e) => setAdjQty(e.target.value)}
                  placeholder="Enter quantity..."
                  className="w-full px-4 py-3 rounded-xl border border-slate-300 text-sm font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Reason / Reference Note
                </label>
                <input
                  type="text"
                  value={adjReason}
                  onChange={(e) => setAdjReason(e.target.value)}
                  placeholder={
                    adjustModal.type === "ADD"
                      ? "e.g. New wholesale delivery"
                      : "e.g. Damaged packet write-off"
                  }
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setAdjustModal(null)}
                  className="px-4 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`px-5 py-2.5 rounded-xl text-white text-sm font-bold ${
                    adjustModal.type === "ADD"
                      ? "bg-emerald-600 hover:bg-emerald-700"
                      : "bg-amber-600 hover:bg-amber-700"
                  }`}
                >
                  Continue to Confirm
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(adjustModal && pendingConfirm)}
        title={
          adjustModal?.type === "ADD"
            ? "Confirm Stock Addition"
            : "Confirm Stock Reduction"
        }
        description={
          adjustModal
            ? `Confirm ${
                adjustModal.type === "ADD" ? "adding" : "reducing"
              } ${adjQty} ${adjustModal.product.unit} ${
                adjustModal.type === "ADD" ? "to" : "from"
              } ${adjustModal.product.product_name}?`
            : ""
        }
        confirmLabel="Confirm"
        cancelLabel="Cancel"
        variant={adjustModal?.type === "ADD" ? "primary" : "warning"}
        loading={submitting}
        onConfirm={executeConfirmedAdjustment}
        onCancel={() => setPendingConfirm(false)}
      />
    </div>
  );
}
