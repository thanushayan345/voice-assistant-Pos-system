import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Plus,
  Search,
  Edit3,
  Trash2,
  Eye,
  X,
  Package,
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

const DEFAULT_CATEGORIES = [
  "Grains & Staples",
  "Groceries",
  "Dairy & Beverages",
  "Beverages",
  "Personal Care",
  "Snacks & Bakery",
  "Household",
  "General",
];

export default function ProductsPage() {
  const { config } = useConfig();
  const sym = config.currency_symbol || "Rs.";
  const units = config.supported_units || [
    "Pieces",
    "Kilograms",
    "Grams",
    "Litres",
    "Bottles",
    "Packets",
    "Boxes",
    "Bags",
  ];

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [error, setError] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    product_name: "",
    category: "Groceries",
    barcode: "",
    purchase_price: "",
    selling_price: "",
    stock_quantity: "0",
    unit: "Pieces",
    low_stock_limit: String(config.low_stock_default ?? 5),
  });

  const [detailProduct, setDetailProduct] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api.getProducts();
      setProducts(list);
    } catch (err) {
      setError(err.message || "Failed to load products.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const categories = useMemo(() => {
    const dynamic = Array.from(new Set(products.map((p) => p.category)));
    const combined = Array.from(new Set([...dynamic, ...DEFAULT_CATEGORIES])).sort();
    return ["All", ...combined];
  }, [products]);

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    return products.filter((p) => {
      if (categoryFilter !== "All" && p.category !== categoryFilter) return false;
      if (!q) return true;
      return (
        p.product_name.toLowerCase().includes(q) ||
        (p.barcode || "").toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
      );
    });
  }, [products, search, categoryFilter]);

  const openAddModal = () => {
    setEditingProduct(null);
    setFormData({
      product_name: "",
      category: "Groceries",
      barcode: "",
      purchase_price: "",
      selling_price: "",
      stock_quantity: "0",
      unit: "Kilograms",
      low_stock_limit: String(config.low_stock_default ?? 5),
    });
    setFormOpen(true);
    setError("");
  };

  const openEditModal = (product) => {
    setEditingProduct(product);
    setFormData({
      product_name: product.product_name,
      category: product.category,
      barcode: product.barcode || "",
      purchase_price: String(product.purchase_price),
      selling_price: String(product.selling_price),
      stock_quantity: String(product.stock_quantity),
      unit: product.unit,
      low_stock_limit: String(product.low_stock_limit),
    });
    setFormOpen(true);
    setError("");
  };

  const openDetailsModal = async (product) => {
    setLoadingDetail(true);
    setDetailProduct(product);
    try {
      const full = await api.getProductById(product.product_id);
      setDetailProduct(full);
    } catch {
      // Keep base product info
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSaveProduct = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload = {
      product_name: formData.product_name.trim(),
      category: formData.category.trim() || "General",
      barcode: formData.barcode.trim() || null,
      purchase_price: Number(formData.purchase_price || 0),
      selling_price: Number(formData.selling_price || 0),
      stock_quantity: Number(formData.stock_quantity || 0),
      unit: formData.unit,
      low_stock_limit: Number(formData.low_stock_limit || 0),
    };

    try {
      if (editingProduct) {
        await api.updateProduct(editingProduct.product_id, payload);
      } else {
        await api.createProduct(payload);
      }
      setFormOpen(false);
      await fetchProducts();
    } catch (err) {
      setError(err.message || "Could not save product.");
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setError("");
    try {
      await api.deleteProduct(deleteTarget.product_id);
      setDeleteTarget(null);
      await fetchProducts();
    } catch (err) {
      setError(err.message || "Could not delete product.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-5 w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-sm text-slate-600">
            Add, edit, search, and configure product prices, units, and low-stock limits.
          </p>
        </div>

        <button
          type="button"
          onClick={openAddModal}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm shadow-xs transition"
        >
          <Plus className="w-4 h-4" />
          Add New Product
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-medium">
          {error}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by product name, category, or barcode..."
            className="w-full pl-11 pr-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {categories.map((c) => (
            <option key={c} value={c}>
              {c === "All" ? "All Categories" : c}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-sm text-slate-500">
            Loading products...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <Package className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-700">No products found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Product</th>
                  <th className="py-3.5 px-4">Category</th>
                  <th className="py-3.5 px-4 text-right">Purchase Price</th>
                  <th className="py-3.5 px-4 text-right">Selling Price</th>
                  <th className="py-3.5 px-4 text-right">Stock</th>
                  <th className="py-3.5 px-4 text-center">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredProducts.map((p) => (
                  <tr key={p.product_id} className="hover:bg-slate-50/80">
                    <td className="py-3.5 px-4">
                      <p className="font-bold text-slate-900">{p.product_name}</p>
                      {p.barcode && (
                        <p className="text-xs text-slate-400">#{p.barcode}</p>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{p.category}</td>
                    <td className="py-3.5 px-4 text-right text-slate-600">
                      {formatCurrency(p.purchase_price, sym)}
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-slate-900">
                      {formatCurrency(p.selling_price, sym)}
                    </td>
                    <td className="py-3.5 px-4 text-right font-semibold text-slate-800">
                      {formatQuantity(p.stock_quantity)}{" "}
                      <span className="text-xs font-normal text-slate-500">{p.unit}</span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <StockBadge
                        stockQuantity={p.stock_quantity}
                        lowStockLimit={p.low_stock_limit}
                      />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openDetailsModal(p)}
                          title="View Details"
                          className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => openEditModal(p)}
                          title="Edit Product"
                          className="p-2 rounded-lg text-indigo-600 hover:bg-indigo-50"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(p)}
                          title="Delete Product"
                          className="p-2 rounded-lg text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 className="w-4 h-4" />
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

      {/* Add / Edit Product Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 overflow-y-auto">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h3 className="text-lg font-extrabold text-slate-900">
                {editingProduct ? `Edit Product #${editingProduct.product_id}` : "Add New Product"}
              </h3>
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Product Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.product_name}
                  onChange={(e) =>
                    setFormData({ ...formData, product_name: e.target.value })
                  }
                  placeholder="e.g. Coconut Oil"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Category *
                  </label>
                  <input
                    type="text"
                    required
                    list="pos-categories-list"
                    value={formData.category}
                    onChange={(e) =>
                      setFormData({ ...formData, category: e.target.value })
                    }
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                  />
                  <datalist id="pos-categories-list">
                    {DEFAULT_CATEGORIES.map((c) => (
                      <option key={c} value={c} />
                    ))}
                  </datalist>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Barcode (Optional)
                  </label>
                  <input
                    type="text"
                    value={formData.barcode}
                    onChange={(e) =>
                      setFormData({ ...formData, barcode: e.target.value })
                    }
                    placeholder="8901..."
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Purchase Price ({sym}) *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    value={formData.purchase_price}
                    onChange={(e) =>
                      setFormData({ ...formData, purchase_price: e.target.value })
                    }
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Selling Price ({sym}) *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    value={formData.selling_price}
                    onChange={(e) =>
                      setFormData({ ...formData, selling_price: e.target.value })
                    }
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm font-bold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Current Stock *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    required
                    value={formData.stock_quantity}
                    onChange={(e) =>
                      setFormData({ ...formData, stock_quantity: e.target.value })
                    }
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Unit *
                  </label>
                  <select
                    value={formData.unit}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm bg-white"
                  >
                    {units.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Low-Stock Limit *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    required
                    value={formData.low_stock_limit}
                    onChange={(e) =>
                      setFormData({ ...formData, low_stock_limit: e.target.value })
                    }
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm"
                  />
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setFormOpen(false)}
                  className="px-4 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold shadow-xs disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingProduct
                    ? "Save Changes"
                    : "Create Product"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Product Detail View Modal */}
      {detailProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 overflow-y-auto">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h3 className="text-lg font-extrabold text-slate-900">
                {detailProduct.product_name}
              </h3>
              <button
                type="button"
                onClick={() => setDetailProduct(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <span className="text-xs text-slate-500 block">Product ID</span>
                  <strong className="text-slate-900">#{detailProduct.product_id}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Category</span>
                  <strong className="text-slate-900">{detailProduct.category}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Purchase Price</span>
                  <strong className="text-slate-900">
                    {formatCurrency(detailProduct.purchase_price, sym)}
                  </strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Selling Price</span>
                  <strong className="text-indigo-700">
                    {formatCurrency(detailProduct.selling_price, sym)} / {detailProduct.unit}
                  </strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Current Stock</span>
                  <strong className="text-slate-900">
                    {formatQuantity(detailProduct.stock_quantity)} {detailProduct.unit}
                  </strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Low-Stock Limit</span>
                  <strong className="text-slate-900">
                    {formatQuantity(detailProduct.low_stock_limit)} {detailProduct.unit}
                  </strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Barcode</span>
                  <strong className="text-slate-900">{detailProduct.barcode || "—"}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Updated At</span>
                  <strong className="text-slate-900 text-xs">
                    {formatDateTime(detailProduct.updated_at)}
                  </strong>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Recent Stock Movements
                </h4>
                {loadingDetail ? (
                  <p className="text-xs text-slate-400">Loading movements...</p>
                ) : !detailProduct.recent_transactions?.length ? (
                  <p className="text-xs text-slate-400">No recent stock movements.</p>
                ) : (
                  <div className="max-h-44 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-xl">
                    {detailProduct.recent_transactions.map((tx) => (
                      <div
                        key={tx.id}
                        className="px-3.5 py-2.5 flex items-center justify-between text-xs"
                      >
                        <div>
                          <span className="font-bold text-slate-800">
                            {tx.transaction_type}
                          </span>
                          <span className="text-slate-500 ml-2">
                            {tx.reason || ""}
                          </span>
                        </div>
                        <span className="font-semibold text-slate-700">
                          {formatQuantity(tx.previous_stock)} →{" "}
                          {formatQuantity(tx.new_stock)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Delete Product Confirmation"
        description={
          deleteTarget
            ? `Are you sure you want to delete '${deleteTarget.product_name}' from the catalog?`
            : ""
        }
        confirmLabel="Confirm Delete"
        cancelLabel="Cancel"
        variant="danger"
        loading={deleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
