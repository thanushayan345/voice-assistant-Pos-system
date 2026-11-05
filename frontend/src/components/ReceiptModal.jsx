import React from "react";
import { Printer, X, CheckCircle2 } from "lucide-react";
import {
  formatCurrency,
  formatDateTime,
  formatQuantity,
} from "../utils/formatters";
import { useConfig } from "../context/ConfigContext";

export default function ReceiptModal({ sale, onClose }) {
  const { config } = useConfig();
  if (!sale) return null;

  const sym = config.currency_symbol || "Rs.";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 overflow-y-auto">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-auto">
        <div className="no-print flex items-center justify-between px-5 py-4 bg-indigo-50 border-b border-indigo-100">
          <div className="flex items-center gap-2.5 text-indigo-900">
            <CheckCircle2 className="w-5 h-5 text-indigo-600" />
            <span className="font-bold text-sm">Sale Completed • Receipt Ready</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-indigo-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div id="printable-receipt-area" className="p-6 text-slate-900 font-mono text-xs sm:text-sm">
          <div className="text-center border-b border-dashed border-slate-300 pb-4 mb-4">
            <h2 className="text-lg font-extrabold tracking-tight font-sans">
              VOICE POS
            </h2>
            <p className="text-xs text-slate-600 font-sans">
              Smart Retail & Inventory Store • Sri Lanka
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Invoice: <span className="font-bold text-slate-800">{sale.invoice_number}</span>
            </p>
            <p className="text-xs text-slate-500">
              Date: {formatDateTime(sale.created_at)}
            </p>
            <p className="text-xs text-slate-500">
              Cashier: {sale.cashier_name} • Channel: {sale.source}
            </p>
          </div>

          <table className="w-full text-left border-collapse mb-4">
            <thead>
              <tr className="border-b border-slate-300 text-slate-600 text-xs">
                <th className="py-1.5">Item</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Price</th>
                <th className="py-1.5 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dashed divide-slate-200">
              {(sale.items || []).map((item) => (
                <tr key={item.id || `${item.product_id}-${item.product_name}`}>
                  <td className="py-2 pr-2 font-sans font-medium text-slate-900">
                    {item.product_name}
                    <span className="block text-[11px] text-slate-400">{item.unit}</span>
                  </td>
                  <td className="py-2 text-center">{formatQuantity(item.quantity)}</td>
                  <td className="py-2 text-right">{formatCurrency(item.unit_price, sym)}</td>
                  <td className="py-2 text-right font-semibold">
                    {formatCurrency(item.subtotal, sym)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="border-t border-dashed border-slate-300 pt-3 space-y-1.5">
            <div className="flex justify-between text-sm font-bold text-slate-900">
              <span>TOTAL ({config.currency})</span>
              <span>{formatCurrency(sale.total_amount, sym)}</span>
            </div>
            <div className="flex justify-between text-xs text-slate-600">
              <span>Cash Received</span>
              <span>{formatCurrency(sale.cash_received, sym)}</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-emerald-700 pt-1 border-t border-slate-200">
              <span>Balance / Change</span>
              <span>{formatCurrency(sale.change_amount, sym)}</span>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-dashed border-slate-300 text-center font-sans text-xs text-slate-500">
            <p className="font-medium text-slate-700">Thank you for shopping with us!</p>
            <p>Please come again.</p>
          </div>
        </div>

        <div className="no-print flex items-center justify-end gap-3 px-5 py-4 bg-slate-50 border-t border-slate-200">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-xs transition"
          >
            <Printer className="w-4 h-4" />
            Print Receipt
          </button>
        </div>
      </div>
    </div>
  );
}
