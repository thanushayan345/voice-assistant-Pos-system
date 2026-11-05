import React from "react";

export default function StockBadge({ stockQuantity, lowStockLimit }) {
  const qty = Number(stockQuantity || 0);
  const limit = Number(lowStockLimit || 0);

  if (qty <= 0) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
        Out of Stock
      </span>
    );
  }

  if (qty <= limit) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
        Low Stock
      </span>
    );
  }

  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
      In Stock
    </span>
  );
}
