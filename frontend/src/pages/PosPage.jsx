import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Search,
  Plus,
  Minus,
  Trash2,
  ShoppingCart,
  Banknote,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { api } from "../services/api";
import { useConfig } from "../context/ConfigContext";
import StockBadge from "../components/StockBadge";
import ConfirmModal from "../components/ConfirmModal";
import ReceiptModal from "../components/ReceiptModal";
import {
  computeLineSubtotal,
  formatCurrency,
  formatQuantity,
  sumMoneyAmounts,
} from "../utils/formatters";

export default function PosPage() {
  const { config } = useConfig();
  const sym = config.currency_symbol || "Rs.";
  const bigAmountThreshold = Number(config.big_amount || 50000);

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  const [cart, setCart] = useState([]);
  const [cashReceived, setCashReceived] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [bigAmountModalOpen, setBigAmountModalOpen] = useState(false);
  const [completedSale, setCompletedSale] = useState(null);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.getProducts();
      setProducts(list);
    } catch (err) {
      setError(err.message || "Could not load products.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const categories = useMemo(() => {
    const unique = Array.from(new Set(products.map((p) => p.category))).sort();
    return ["All", ...unique];
  }, [products]);

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    return products.filter((p) => {
      const catOk = selectedCategory === "All" || p.category === selectedCategory;
      if (!catOk) return false;
      if (!q) return true;
      return (
        p.product_name.toLowerCase().includes(q) ||
        (p.barcode || "").toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
      );
    });
  }, [products, search, selectedCategory]);

  const addToCart = (product) => {
    setError("");
    const available = Number(product.stock_quantity || 0);
    if (available <= 0) {
      setError(`'${product.product_name}' is out of stock.`);
      return;
    }

    setCart((prev) => {
      const existing = prev.find((item) => item.product_id === product.product_id);
      if (existing) {
        const nextQty = parseFloat((existing.quantity + 1).toFixed(3));
        if (nextQty > available) {
          setError(
            `Only ${formatQuantity(available)} ${product.unit} of ${product.product_name} available.`
          );
          return prev;
        }
        return prev.map((item) =>
          item.product_id === product.product_id
            ? { ...item, quantity: nextQty }
            : item
        );
      }
      const initialQty = available >= 1 ? 1 : available;
      return [
        ...prev,
        {
          product_id: product.product_id,
          product_name: product.product_name,
          unit: product.unit,
          unit_price: Number(product.selling_price),
          max_stock: available,
          quantity: initialQty,
        },
      ];
    });
  };

  const updateCartQty = (productId, newQtyRaw) => {
    setError("");
    const parsed = Number(newQtyRaw);
    if (Number.isNaN(parsed)) return;

    setCart((prev) =>
      prev
        .map((item) => {
          if (item.product_id !== productId) return item;
          if (parsed <= 0) return null;
          if (parsed > item.max_stock) {
            setError(
              `Cannot exceed available stock (${formatQuantity(item.max_stock)} ${item.unit}) for ${item.product_name}.`
            );
            return { ...item, quantity: item.max_stock };
          }
          return { ...item, quantity: parseFloat(parsed.toFixed(3)) };
        })
        .filter(Boolean)
    );
  };

  const removeFromCart = (productId) => {
    setCart((prev) => prev.filter((item) => item.product_id !== productId));
  };

  const clearCart = () => {
    setCart([]);
    setCashReceived("");
    setError("");
  };

  const cartLinesWithSubtotals = useMemo(
    () =>
      cart.map((item) => ({
        ...item,
        subtotal: computeLineSubtotal(item.quantity, item.unit_price),
      })),
    [cart]
  );

  const totalBill = useMemo(
    () => sumMoneyAmounts(cartLinesWithSubtotals.map((l) => l.subtotal)),
    [cartLinesWithSubtotals]
  );

  const cashNumber = cashReceived === "" ? 0 : Number(cashReceived);
  const changeAmount = Math.max(
    0,
    Math.round((cashNumber - totalBill) * 100) / 100
  );
  const cashSufficient = cashNumber >= totalBill && totalBill > 0;
  const exceedsBigAmount = totalBill > bigAmountThreshold;

  const executeCheckout = async (confirmedBig = false) => {
    if (cart.length === 0) return;
    if (!cashSufficient) {
      setError(`Cash received must be at least ${formatCurrency(totalBill, sym)}.`);
      return;
    }

    if (exceedsBigAmount && !confirmedBig) {
      setBigAmountModalOpen(true);
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const sale = await api.createSale({
        items: cart.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
        })),
        cash_received: cashNumber,
        payment_method: "CASH",
        confirm_big_amount: confirmedBig,
      });

      setBigAmountModalOpen(false);
      setCompletedSale(sale);
      clearCart();
      await loadProducts();
    } catch (err) {
      if (err.code === "BIG_AMOUNT_CONFIRMATION_REQUIRED") {
        setBigAmountModalOpen(true);
      } else {
        setError(err.message || "Failed to complete sale.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4 w-full">
      {error && (
        <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Product Selection Grid (Left 8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs space-y-3">
            <div className="relative">
              <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search product by name, category, or barcode..."
                className="w-full pl-11 pr-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition ${
                    selectedCategory === cat
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-sm text-slate-500">
              Loading product catalog...
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-sm text-slate-500">
              No products match your search.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3.5">
              {filteredProducts.map((product) => {
                const outOfStock = Number(product.stock_quantity) <= 0;
                const inCartItem = cart.find((c) => c.product_id === product.product_id);
                return (
                  <button
                    key={product.product_id}
                    type="button"
                    disabled={outOfStock}
                    onClick={() => addToCart(product)}
                    className={`text-left p-4 rounded-2xl border transition relative ${
                      outOfStock
                        ? "bg-slate-100 border-slate-200 opacity-60 cursor-not-allowed"
                        : inCartItem
                        ? "bg-indigo-50/70 border-indigo-400 shadow-xs"
                        : "bg-white border-slate-200 hover:border-indigo-400 hover:shadow-md"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-extrabold text-slate-900 text-base">
                          {product.product_name}
                        </p>
                        <p className="text-xs text-slate-500">{product.category}</p>
                      </div>
                      <StockBadge
                        stockQuantity={product.stock_quantity}
                        lowStockLimit={product.low_stock_limit}
                      />
                    </div>

                    <div className="mt-4 flex items-end justify-between">
                      <div>
                        <p className="text-lg font-extrabold text-slate-900">
                          {formatCurrency(product.selling_price, sym)}
                        </p>
                        <p className="text-xs text-slate-500">
                          Stock: {formatQuantity(product.stock_quantity)} {product.unit}
                        </p>
                      </div>

                      {inCartItem ? (
                        <span className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-xs font-extrabold">
                          In Cart: {formatQuantity(inCartItem.quantity)}
                        </span>
                      ) : (
                        <span className="p-2 rounded-xl bg-slate-100 text-slate-700">
                          <Plus className="w-4 h-4" />
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Billing Cart Panel (Right 4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <ShoppingCart className="w-5 h-5 text-indigo-400" />
              <h3 className="font-extrabold text-base">Current Bill ({cart.length})</h3>
            </div>
            {cart.length > 0 && (
              <button
                type="button"
                onClick={clearCart}
                className="text-xs font-semibold text-rose-300 hover:text-rose-200"
              >
                Clear Cart
              </button>
            )}
          </div>

          {cartLinesWithSubtotals.length === 0 ? (
            <div className="p-10 text-center space-y-2">
              <ShoppingCart className="w-10 h-10 text-slate-300 mx-auto" />
              <p className="text-sm font-semibold text-slate-600">Cart is empty</p>
              <p className="text-xs text-slate-400">
                Click any product card on the left to add items to the bill.
              </p>
            </div>
          ) : (
            <div className="p-5 space-y-4">
              <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto pr-1">
                {cartLinesWithSubtotals.map((item) => (
                  <div key={item.product_id} className="py-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-bold text-slate-900">
                          {item.product_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatCurrency(item.unit_price, sym)} / {item.unit}
                        </p>
                      </div>
                      <p className="text-sm font-extrabold text-slate-900">
                        {formatCurrency(item.subtotal, sym)}
                      </p>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() =>
                            updateCartQty(
                              item.product_id,
                              Math.max(0, Number((item.quantity - 1).toFixed(3)))
                            )
                          }
                          className="p-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <input
                          type="number"
                          min="0.001"
                          step="any"
                          max={item.max_stock}
                          value={item.quantity}
                          onChange={(e) =>
                            updateCartQty(item.product_id, e.target.value)
                          }
                          className="w-20 text-center py-1 px-2 rounded-lg border border-slate-300 text-sm font-bold"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            updateCartQty(
                              item.product_id,
                              Number((item.quantity + 1).toFixed(3))
                            )
                          }
                          className="p-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() => removeFromCart(item.product_id)}
                        className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50"
                        title="Remove item"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-base font-bold text-slate-700">Total Bill</span>
                  <span className="text-2xl font-extrabold text-indigo-700">
                    {formatCurrency(totalBill, sym)}
                  </span>
                </div>

                {exceedsBigAmount && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs font-semibold flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    Exceeds {formatCurrency(bigAmountThreshold, sym)} high-value threshold — confirmation required.
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                    Cash Received ({sym})
                  </label>
                  <div className="relative">
                    <Banknote className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={cashReceived}
                      onChange={(e) => setCashReceived(e.target.value)}
                      placeholder={`Enter cash (min ${totalBill.toFixed(2)})`}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 text-base font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => setCashReceived(String(totalBill))}
                      className="px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-800 text-xs font-bold border border-indigo-200"
                    >
                      Exact ({formatCurrency(totalBill, sym)})
                    </button>
                    {[500, 1000, 2000, 5000].map((noteVal) => (
                      <button
                        key={noteVal}
                        type="button"
                        onClick={() =>
                          setCashReceived(
                            String(Math.max(noteVal, Math.ceil(totalBill / noteVal) * noteVal))
                          )
                        }
                        className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold"
                      >
                        {sym} {noteVal.toLocaleString()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Customer Balance / Change
                  </span>
                  <span
                    className={`text-lg font-extrabold ${
                      cashSufficient ? "text-emerald-700" : "text-slate-400"
                    }`}
                  >
                    {cashSufficient ? formatCurrency(changeAmount, sym) : `${sym} 0.00`}
                  </span>
                </div>

                <button
                  type="button"
                  disabled={submitting || !cashSufficient}
                  onClick={() => executeCheckout(false)}
                  className="w-full py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-sm shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  {submitting
                    ? "Processing Payment..."
                    : `Complete Payment • ${formatCurrency(totalBill, sym)}`}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmModal
        isOpen={bigAmountModalOpen}
        title="High-Value Sale Confirmation"
        description={`This bill total of ${formatCurrency(
          totalBill,
          sym
        )} exceeds the configured threshold of ${formatCurrency(
          bigAmountThreshold,
          sym
        )}. Confirm processing this payment?`}
        confirmLabel="Confirm & Process Bill"
        cancelLabel="Cancel"
        variant="warning"
        loading={submitting}
        onConfirm={() => executeCheckout(true)}
        onCancel={() => setBigAmountModalOpen(false)}
      />

      <ReceiptModal sale={completedSale} onClose={() => setCompletedSale(null)} />
    </div>
  );
}
