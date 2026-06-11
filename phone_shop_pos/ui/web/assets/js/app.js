/* ui/web/assets/js/app.js */

// Global State
let currentUser = null;
let currentTab = "dashboard";
let catalogProducts = [];
let customerList = [];
let activeCart = [];
let shopSettings = {};

// Modal bindings helper
const modalOverlay = document.getElementById("global-modal");

// 1. Connection to Python QWebChannel Backend Bridge
function callPython(action, payload, callback) {
    if (window.backend) {
        window.backend.execute(action, JSON.stringify(payload || {}), function(responseJson) {
            try {
                const response = JSON.parse(responseJson);
                if (callback) callback(response);
            } catch (e) {
                console.error("Failed to parse JSON response for action: " + action, e, responseJson);
                showToast("JSON Parsing error: " + e.message, "error");
            }
        });
    } else {
        console.warn("Python QWebChannel is not connected. Action ignored: " + action);
    }
}

// 2. Global Toast Notifications
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <span style="cursor:pointer; font-weight:bold; font-size:1.1rem; opacity:0.8;" onclick="this.parentElement.remove()">&times;</span>
    `;
    container.appendChild(toast);
    
    // Animate slide-in
    setTimeout(() => toast.classList.add("show"), 10);
    
    // Auto-remove after 4s
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// 3. Global Modal Window Management
function openModal(title, bodyHtml, footerHtml) {
    document.getElementById("modal-title").innerText = title;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    document.getElementById("modal-footer").innerHTML = footerHtml || "";
    modalOverlay.classList.add("active");
}

function closeModal() {
    modalOverlay.classList.remove("active");
}

document.getElementById("modal-close-btn").addEventListener("click", closeModal);

// 4. SPA Page Dynamic Router & Injector
function loadPage(pageName) {
    currentTab = pageName;
    const contentArea = document.getElementById("content-area");
    
    // Show skeleton loading state
    contentArea.innerHTML = `
        <div class="skeleton-title skeleton"></div>
        <div class="glass-card" style="height: 150px; margin-bottom: 20px;">
            <div class="skeleton-text skeleton"></div>
            <div class="skeleton-text skeleton" style="width: 60%"></div>
        </div>
        <div class="metrics-grid">
            <div class="skeleton" style="height: 120px; border-radius: 16px;"></div>
            <div class="skeleton" style="height: 120px; border-radius: 16px;"></div>
        </div>
    `;

    fetch(`${pageName}.html`)
        .then(response => {
            if (!response.ok) throw new Error("Network response error loading page");
            return response.text();
        })
        .then(html => {
            contentArea.innerHTML = html;
            
            // Execute Page Specific Initializations
            switch(pageName) {
                case "dashboard":
                    initDashboard();
                    break;
                case "billing":
                    initBilling();
                    break;
                case "products":
                    initProducts();
                    break;
                case "inventory":
                    initInventory();
                    break;
                case "customers":
                    initCustomers();
                    break;
                case "reports":
                    initReports();
                    break;
                case "settings":
                    initSettings();
                    break;
            }
        })
        .catch(err => {
            console.error("Error loading page: " + pageName, err);
            contentArea.innerHTML = `<div class="glass-card animated-page" style="color:var(--danger); font-weight:bold;">Error loading section: ${err.message}</div>`;
        });
}

// 5. User Authentication / Login Form Handlers
document.getElementById("login-form").addEventListener("submit", function(e) {
    e.preventDefault();
    const u = document.getElementById("username").value.trim();
    const p = document.getElementById("password").value.trim();
    
    callPython("login", { username: u, password: p }, function(res) {
        if (res.success) {
            currentUser = res.user;
            
            // Setup Workspace UI
            document.getElementById("display-username").innerText = currentUser.username;
            document.getElementById("display-role").innerText = currentUser.role === 'admin' ? 'ADMINISTRATOR' : 'CASHIER';
            
            // Role Based Content Visibility
            if (currentUser.role === 'cashier') {
                document.querySelectorAll(".admin-only").forEach(el => el.style.display = 'none');
            } else {
                document.querySelectorAll(".admin-only").forEach(el => el.style.display = 'block');
            }
            
            // Fade-out Login Overlay and Show Main Interface
            document.getElementById("login-screen").style.display = "none";
            document.getElementById("app-container").style.display = "flex";
            
            showToast(`Welcome back, ${currentUser.username}!`, "success");
            
            // Load Default Dashboard Page
            loadPage("dashboard");
        } else {
            showToast(res.message, "error");
        }
    });
});

// Sidebar Logout Click
document.getElementById("sidebar-logout").addEventListener("click", function() {
    if (confirm("Are you sure you want to sign out of the terminal?")) {
        currentUser = null;
        document.getElementById("username").value = "";
        document.getElementById("password").value = "";
        
        document.getElementById("app-container").style.display = "none";
        document.getElementById("login-screen").style.display = "flex";
        showToast("Signed out successfully", "warning");
    }
});

// Sidebar Link Navigation Swaps
document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", function(e) {
        e.preventDefault();
        
        // Remove Active UI status from old menu item
        document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
        
        // Add Active status
        this.classList.add("active");
        
        // Load Page
        const page = this.getAttribute("data-page");
        loadPage(page);
    });
});

// ================= PAGE INITIALIZATIONS & FUNCTIONS =================

// --- 1. DASHBOARD OVERVIEW ---
function initDashboard() {
    // Refresh Button Hook
    document.getElementById("refresh-dashboard-btn").addEventListener("click", initDashboard);

    // Binds Welcome Title
    document.getElementById("dashboard-welcome").innerText = `Welcome, ${currentUser.username}!`;

    // Fetch Dashboard KPIs
    callPython("get_dashboard_metrics", {}, function(res) {
        if (res.success) {
            const m = res.metrics;
            document.getElementById("kpi-today-revenue").innerText = `Rs. ${parseFloat(m.today_revenue || 0).toFixed(2)}`;
            document.getElementById("kpi-month-revenue").innerText = `Rs. ${parseFloat(m.month_revenue || 0).toFixed(2)}`;
            document.getElementById("kpi-today-sales").innerText = `${m.today_transactions || 0} sales`;
            document.getElementById("kpi-total-stock").innerText = `${m.total_stock || 0} units`;
            
            // Render Low Stock alerts
            const lowStockBody = document.querySelector("#low-stock-table tbody");
            lowStockBody.innerHTML = "";
            document.getElementById("low-stock-count-badge").innerText = `${res.low_stock.length} items`;
            
            if (res.low_stock.length === 0) {
                lowStockBody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--success);">✔ No inventory alerts</td></tr>`;
            } else {
                res.low_stock.forEach(item => {
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td>${item.name}</td>
                        <td style="color:var(--danger); font-weight:bold;">${item.stock} left</td>
                    `;
                    lowStockBody.appendChild(row);
                });
            }

            // Draw Weekly Sales Chart via Chart.js
            const ctx = document.getElementById("weekly-trend-chart").getContext("2d");
            const labels = res.trend.map(t => t[0]);
            const data = res.trend.map(t => t[1]);

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Revenue (Rs.)',
                        data: data,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.15)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointBackgroundColor: '#6366f1',
                        pointBorderColor: '#090d16',
                        pointBorderWidth: 2,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            grid: { color: 'rgba(51, 65, 85, 0.3)' },
                            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans' } }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans' } }
                        }
                    }
                }
            });
        } else {
            showToast("Failed to fetch dashboard metrics: " + res.message, "error");
        }
    });
}

// --- 2. BILLING SCREEN / POS ---
function initBilling() {
    // Bind scanner form
    document.getElementById("pos-scan-form").addEventListener("submit", function(e) {
        e.preventDefault();
        const code = document.getElementById("pos-scan-input").value.trim();
        if (!code) return;
        document.getElementById("pos-scan-input").value = "";
        
        callPython("scan_barcode", { barcode: code }, function(res) {
            if (res.success) {
                // If success, add product to checkout cart array
                addProductToCart(res.product, code);
            } else {
                showToast(res.message, "error");
            }
        });
    });

    // Binds Catalog Search
    document.getElementById("pos-catalog-search").addEventListener("input", function() {
        const query = this.value.trim().toLowerCase();
        filterBillingCatalog(query);
    });

    // Binds Discount Value Action Listener
    document.getElementById("pos-discount-input").addEventListener("input", function() {
        calculateBillingTotals();
    });

    // Checkout Buttons Action
    document.getElementById("pos-clear-cart-btn").addEventListener("click", clearBillingCart);
    document.getElementById("pos-checkout-btn").addEventListener("click", openCheckoutModal);
    
    // Customer additions shortcuts
    document.getElementById("pos-add-customer-btn").addEventListener("click", openQuickCustomerModal);

    // Load POS Catalogs Data
    refreshPOSCatalog();
}

function refreshPOSCatalog() {
    callPython("get_products", {}, function(res) {
        if (res.success) {
            catalogProducts = res.products;
            
            // Fetch tax rates
            callPython("get_settings", {}, function(settingsRes) {
                if (settingsRes.success) {
                    shopSettings = settingsRes.settings;
                    document.getElementById("pos-tax-title").innerText = `GST (${parseFloat(shopSettings.taxRate || 18.0)}%)`;
                }
                
                // Fetch Customers Combo listings
                callPython("get_customers", {}, function(custRes) {
                    if (custRes.success) {
                        customerList = custRes.customers;
                        const select = document.getElementById("pos-customer-select");
                        select.innerHTML = '<option value="">-- Guest Customer --</option>';
                        customerList.forEach(c => {
                            select.innerHTML += `<option value="${c.id}">${c.customer_name} (${c.phone})</option>`;
                        });
                    }
                    
                    renderBillingCatalog(catalogProducts);
                    renderBillingCart();
                });
            });
        }
    });
}

function renderBillingCatalog(products) {
    const tbody = document.querySelector("#pos-catalog-table tbody");
    tbody.innerHTML = "";
    
    // Filters only items in stock
    const inStock = products.filter(p => p.quantity > 0);
    
    if (inStock.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No products in stock</td></tr>`;
        return;
    }

    inStock.forEach(p => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td style="font-family:monospace;font-weight:bold;">${p.barcode}</td>
            <td>${p.brand} ${p.product_name}</td>
            <td style="text-align:right;">Rs. ${parseFloat(p.selling_price).toFixed(2)}</td>
            <td style="text-align:center;font-weight:bold;color:var(--success);">${p.quantity} left</td>
        `;
        
        // Double click to add product
        row.addEventListener("dblclick", () => {
            addProductToCart(p);
        });
        
        tbody.appendChild(row);
    });
}

function filterBillingCatalog(query) {
    const filtered = catalogProducts.filter(p => 
        p.barcode.toLowerCase().includes(query) || 
        p.product_name.toLowerCase().includes(query) || 
        p.brand.toLowerCase().includes(query)
    );
    renderBillingCatalog(filtered);
}

function addProductToCart(product, scannedCode = null) {
    // 1. Fetch available IMEIs for product ID
    callPython("get_imeis", { product_id: product.id, status: "available" }, function(imeiRes) {
        const availImeis = imeiRes.success ? imeiRes.imeis : [];
        const requiresImei = availImeis.length > 0;
        
        // Find if product is already in cart
        const existing = activeCart.find(item => item.product.id === product.id);
        
        if (requiresImei) {
            // Check if scannedCode is an IMEI itself
            if (scannedCode && availImeis.some(i => i.imei === scannedCode)) {
                linkImeiToCart(product, scannedCode);
            } else {
                // Open IMEI selection modal
                openImeiSelectionModal(product, availImeis);
            }
        } else {
            // Standard accessories/devices
            if (existing) {
                if (existing.quantity + 1 > product.quantity) {
                    showToast(`Insufficient stock! Only ${product.quantity} units available.`, "error");
                    return;
                }
                existing.quantity += 1;
                existing.total_price = existing.quantity * product.selling_price;
            } else {
                activeCart.push({
                    product: product,
                    quantity: 1,
                    selling_price: product.selling_price,
                    total_price: product.selling_price,
                    imeis: []
                });
            }
            renderBillingCart();
            showToast(`Added ${product.brand} ${product.product_name} to cart.`);
        }
    });
}

function openImeiSelectionModal(product, imeis) {
    let body = `
        <p style="margin-bottom:15px; font-size:0.9rem; color:var(--text-muted);">
            This device has registered serial IMEIs. Select one to proceed:
        </p>
        <div class="form-group">
            <label>Available Serial Codes</label>
            <select id="imei-modal-select" class="form-control" style="font-family:monospace;">
    `;
    imeis.forEach(i => {
        body += `<option value="${i.imei}">${i.imei} (Added ${i.added_date.substring(0, 10)})</option>`;
    });
    body += `
            </select>
        </div>
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="confirm-imei-btn">Link Selected IMEI</button>
    `;
    
    openModal(`Link IMEI: ${product.brand} ${product.product_name}`, body, footer);
    
    document.getElementById("confirm-imei-btn").addEventListener("click", () => {
        const selected = document.getElementById("imei-modal-select").value;
        closeModal();
        linkImeiToCart(product, selected);
    });
}

function linkImeiToCart(product, imeiCode) {
    // Fetch instance details matching selected IMEI
    callPython("get_imei_details", { imei: imeiCode }, function(detailsRes) {
        if (detailsRes.success && detailsRes.details) {
            const pInstance = detailsRes.details;
            
            // Check if this physical product instance ID is already in cart
            const alreadyInCart = activeCart.some(item => item.product.id === pInstance.id || item.imeis.includes(imeiCode));
            if (alreadyInCart) {
                showToast("Device with this IMEI is already in checkout cart.", "warning");
                return;
            }
            
            // Add physical device instance to checkout cart
            activeCart.push({
                product: {
                    id: pInstance.id,
                    barcode: pInstance.sku,
                    product_name: pInstance.model,
                    brand: pInstance.brand,
                    purchase_price: pInstance.purchase_price || 0,
                    selling_price: pInstance.selling_price || product.selling_price
                },
                quantity: 1,
                selling_price: pInstance.selling_price || product.selling_price,
                total_price: pInstance.selling_price || product.selling_price,
                imeis: [imeiCode]
            });
            
            renderBillingCart();
            showToast(`Linked IMEI ${imeiCode} successfully.`);
        } else {
            showToast("Failed to link serial code", "error");
        }
    });
}

function renderBillingCart() {
    const list = document.getElementById("pos-cart-list");
    list.innerHTML = "";
    
    if (activeCart.length === 0) {
        list.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding-top: 50px;" id="cart-empty-message">Cart is currently empty. Double click a catalog item or scan code to add.</div>`;
        calculateBillingTotals();
        return;
    }

    activeCart.forEach((item, idx) => {
        const div = document.createElement("div");
        div.className = "cart-item";
        
        let subText = item.imeis.length > 0 ? `<span class="cart-item-imei">IMEI: ${item.imeis[0]}</span>` : `<span style="font-size:0.75rem;color:var(--text-muted);">Barcode: ${item.product.barcode}</span>`;
        
        div.innerHTML = `
            <div class="cart-item-info">
                <span class="cart-item-name">${item.product.brand} ${item.product.product_name}</span>
                ${subText}
            </div>
            <div class="cart-item-meta">
                <div class="cart-qty-control">
                    <button class="cart-qty-btn" ${item.imeis.length > 0 ? "disabled" : ""} onclick="adjustCartQty(${idx}, -1)">-</button>
                    <span class="cart-qty-val">${item.quantity}</span>
                    <button class="cart-qty-btn" ${item.imeis.length > 0 ? "disabled" : ""} onclick="adjustCartQty(${idx}, 1)">+</button>
                </div>
                <span class="cart-item-total">Rs. ${parseFloat(item.total_price).toFixed(2)}</span>
                <button class="cart-item-remove" onclick="removeCartItem(${idx})" title="Remove item">
                    &times;
                </button>
            </div>
        `;
        list.appendChild(div);
    });
    
    calculateBillingTotals();
}

window.adjustCartQty = function(index, change) {
    const item = activeCart[index];
    const newQty = item.quantity + change;
    
    if (newQty <= 0) {
        removeCartItem(index);
        return;
    }
    
    if (newQty > item.product.quantity) {
        showToast(`Insufficient inventory stock! Only ${item.product.quantity} items available.`, "error");
        return;
    }
    
    item.quantity = newQty;
    item.total_price = item.quantity * item.selling_price;
    renderBillingCart();
};

window.removeCartItem = function(index) {
    activeCart.splice(index, 1);
    renderBillingCart();
    showToast("Item removed from register cart", "warning");
};

function calculateBillingTotals() {
    const subtotal = activeCart.reduce((sum, item) => sum + item.total_price, 0);
    const discVal = parseFloat(document.getElementById("pos-discount-input").value) || 0;
    
    const taxRate = parseFloat(shopSettings.taxRate || 18.0);
    const net = Math.max(0.0, subtotal - discVal);
    const gst = net * (taxRate / 100.0);
    const total = net + gst;
    
    document.getElementById("pos-subtotal").innerText = `Rs. ${subtotal.toFixed(2)}`;
    document.getElementById("pos-tax-val").innerText = `Rs. ${gst.toFixed(2)}`;
    document.getElementById("pos-grand-total").innerText = `Rs. ${total.toFixed(2)}`;
}

function clearBillingCart() {
    if (activeCart.length === 0) return;
    if (confirm("Are you sure you want to reset the shopping checkout register?")) {
        activeCart = [];
        renderBillingCart();
    }
}

function openQuickCustomerModal() {
    const body = `
        <div class="form-group">
            <label>Customer Name *</label>
            <input type="text" id="qc-name" class="form-control" required placeholder="Enter customer name">
        </div>
        <div class="form-group">
            <label>Phone Number *</label>
            <input type="text" id="qc-phone" class="form-control" required placeholder="Enter 10-digit number">
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="qc-submit-btn">Save Profile</button>
    `;
    openModal("Register Quick Customer", body, footer);
    
    document.getElementById("qc-submit-btn").addEventListener("click", () => {
        const name = document.getElementById("qc-name").value.trim();
        const phone = document.getElementById("qc-phone").value.trim();
        
        if (!name || !phone) {
            showToast("All fields are required", "error");
            return;
        }
        
        callPython("add_customer", { customer_name: name, phone: phone, address: "" }, function(res) {
            if (res.success) {
                closeModal();
                showToast("Customer registered successfully.");
                refreshPOSCatalog(); // Reload customer select dropdown
                setTimeout(() => {
                    document.getElementById("pos-customer-select").value = res.customer.id;
                }, 200);
            } else {
                showToast(res.message, "error");
            }
        });
    });
}

function openCheckoutModal() {
    if (activeCart.length === 0) {
        showToast("Cart is empty", "warning");
        return;
    }
    
    const subtotal = activeCart.reduce((sum, item) => sum + item.total_price, 0);
    const discVal = parseFloat(document.getElementById("pos-discount-input").value) || 0;
    const taxRate = parseFloat(shopSettings.taxRate || 18.0);
    const net = Math.max(0.0, subtotal - discVal);
    const gst = net * (taxRate / 100.0);
    const total = net + gst;

    const body = `
        <div class="form-group">
            <label>Payment Mode *</label>
            <select id="checkout-payment-mode" class="form-control">
                <option value="Cash">Cash Payment</option>
                <option value="UPI / QR Code">UPI / QR Code Scan</option>
                <option value="Debit/Credit Card">Debit/Credit Card swipe</option>
            </select>
        </div>
        <div style="background-color:rgba(16,185,129,0.1); border-radius:8px; padding:15px; text-align:center; margin-top:20px;">
            <div style="font-size:0.85rem; color:var(--text-muted);">Amount Due</div>
            <div style="font-size:1.6rem; font-weight:800; color:var(--success); margin-top:5px;">Rs. ${total.toFixed(2)}</div>
        </div>
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-success" id="checkout-finalize-btn" style="font-weight:bold;">PAY & PRINT RECEIPT</button>
    `;
    
    openModal("Finalize Invoice Checkout", body, footer);
    
    document.getElementById("checkout-finalize-btn").addEventListener("click", () => {
        const payMode = document.getElementById("checkout-payment-mode").value;
        const custSelect = document.getElementById("pos-customer-select").value;
        const customerId = custSelect ? parseInt(custSelect) : null;
        
        // Format cart for backend Transaction
        const formattedCart = activeCart.map(item => ({
            product_id: item.product.id,
            quantity: item.quantity
        }));
        
        closeModal();
        
        // Show loader skeleton
        document.getElementById("content-area").innerHTML = `<div class="glass-card skeleton" style="height:350px;text-align:center;padding-top:100px;"><h3>Processing checkout register order transaction...</h3></div>`;
        
        callPython("create_invoice", {
            customer_id: customerId,
            cart_items: formattedCart,
            discount: discVal,
            payment_method: payMode
        }, function(res) {
            if (res.success) {
                showToast(`Checkout successful! Created Invoice ${res.invoice_no}`);
                activeCart = [];
                
                // Reload section
                loadPage("billing");
                
                // Trigger auto reprint receipt in text editor
                callPython("reprint_receipt", { invoice_no: res.invoice_no });
            } else {
                showToast("Checkout failed: " + res.message, "error");
                // Reload POS page to restore screen
                loadPage("billing");
            }
        });
    });
}

// --- 3. PRODUCTS CATALOG ---
function initProducts() {
    // Add Product Modal trigger
    const addBtn = document.getElementById("add-product-modal-btn");
    if (addBtn) {
        addBtn.addEventListener("click", () => openProductFormModal());
    }

    // Reset filters
    document.getElementById("product-reset-btn").addEventListener("click", () => {
        document.getElementById("product-search-input").value = "";
        refreshProductsList();
    });

    // Binds Search
    document.getElementById("product-search-input").addEventListener("input", function() {
        const query = this.value.trim().toLowerCase();
        filterProductsTable(query);
    });

    refreshProductsList();
}

function refreshProductsList() {
    callPython("get_products", {}, function(res) {
        if (res.success) {
            catalogProducts = res.products;
            renderProductsTable(catalogProducts);
        }
    });
}

function renderProductsTable(products) {
    const tbody = document.querySelector("#products-table tbody");
    tbody.innerHTML = "";

    if (products.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-muted);">No products registered</td></tr>`;
        return;
    }

    products.forEach(p => {
        const row = document.createElement("tr");
        
        let actionColumn = "";
        if (currentUser.role === 'admin') {
            actionColumn = `
                <td style="text-align:center; display:flex; gap:6px; justify-content:center;">
                    <button class="btn btn-secondary btn-icon-only" onclick="openProductFormModal(${p.id})" title="Edit Details">✏</button>
                    <button class="btn btn-secondary btn-icon-only" onclick="previewBarcode('${p.barcode}', '${p.brand} ${p.product_name}')" title="Preview Barcode">👁</button>
                    <button class="btn btn-secondary btn-icon-only" onclick="printBarcode('${p.barcode}', '${p.brand} ${p.product_name}', ${p.selling_price})" title="Print Label">🖨</button>
                    <button class="btn btn-secondary btn-icon-only" onclick="regenerateBarcode(${p.id})" title="Regenerate Barcode">🔄</button>
                    <button class="btn btn-danger btn-icon-only" onclick="deleteProduct(${p.id}, '${p.brand} ${p.product_name}')" title="Delete Product">&times;</button>
                </td>
            `;
        } else {
            actionColumn = `<td style="text-align:center;"><span class="badge badge-info">View Mode</span></td>`;
        }

        row.innerHTML = `
            <td style="font-family:monospace;font-weight:bold;">${p.barcode}</td>
            <td>${p.brand}</td>
            <td>${p.product_name}</td>
            <td><span class="badge badge-info">${p.category}</span></td>
            <td style="text-align:center; font-weight:bold; color:${p.quantity <= 5 ? 'var(--danger)' : 'var(--success)'};">${p.quantity} units</td>
            <td style="text-align:right;">Rs. ${parseFloat(p.purchase_price).toFixed(2)}</td>
            <td style="text-align:right; font-weight:bold;">Rs. ${parseFloat(p.selling_price).toFixed(2)}</td>
            ${actionColumn}
        `;
        tbody.appendChild(row);
    });
}

function filterProductsTable(query) {
    const filtered = catalogProducts.filter(p => 
        p.barcode.toLowerCase().includes(query) || 
        p.product_name.toLowerCase().includes(query) || 
        p.brand.toLowerCase().includes(query) ||
        p.category.toLowerCase().includes(query)
    );
    renderProductsTable(filtered);
}

window.openProductFormModal = function(productId = null) {
    const isEdit = productId !== null;
    const targetProduct = isEdit ? catalogProducts.find(p => p.id === productId) : null;
    
    const body = `
        <form id="modal-product-form">
            <div class="form-group">
                <label>Barcode / SKU</label>
                <input type="text" class="form-control" value="${isEdit ? targetProduct.barcode : '[AUTO GENERATED ON SAVE]'}" readonly disabled style="font-family:monospace;">
            </div>
            <div class="form-group">
                <label>Brand Name *</label>
                <input type="text" id="m-prod-brand" class="form-control" value="${isEdit ? targetProduct.brand : ''}" required placeholder="e.g. Apple, Samsung">
            </div>
            <div class="form-group">
                <label>Product Model Name *</label>
                <input type="text" id="m-prod-name" class="form-control" value="${isEdit ? targetProduct.product_name : ''}" required placeholder="e.g. iPhone 15, S24">
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>Category *</label>
                    <select id="m-prod-cat" class="form-control" required>
                        <option value="Phones" ${isEdit && targetProduct.category === 'Phones' ? 'selected' : ''}>Phones</option>
                        <option value="Accessories" ${isEdit && targetProduct.category === 'Accessories' ? 'selected' : ''}>Accessories</option>
                        <option value="Tablets" ${isEdit && targetProduct.category === 'Tablets' ? 'selected' : ''}>Tablets</option>
                        <option value="Smartwatches" ${isEdit && targetProduct.category === 'Smartwatches' ? 'selected' : ''}>Smartwatches</option>
                        <option value="Other" ${isEdit && targetProduct.category === 'Other' ? 'selected' : ''}>Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Initial Stock *</label>
                    <input type="number" id="m-prod-qty" class="form-control" min="0" value="${isEdit ? targetProduct.quantity : '0'}" ${isEdit ? 'disabled readonly' : ''} required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>Purchase Cost (Rs.) *</label>
                    <input type="number" id="m-prod-cost" class="form-control" min="0" step="0.01" value="${isEdit ? targetProduct.purchase_price : ''}" required>
                </div>
                <div class="form-group">
                    <label>Selling Price (Rs.) *</label>
                    <input type="number" id="m-prod-price" class="form-control" min="0" step="0.01" value="${isEdit ? targetProduct.selling_price : ''}" required>
                </div>
            </div>
        </form>
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="m-prod-submit">Save Details</button>
    `;
    
    openModal(isEdit ? "Edit Product Details" : "Register New Product", body, footer);
    
    document.getElementById("m-prod-submit").addEventListener("click", () => {
        const brand = document.getElementById("m-prod-brand").value.trim();
        const name = document.getElementById("m-prod-name").value.trim();
        const cat = document.getElementById("m-prod-cat").value;
        const qty = parseInt(document.getElementById("m-prod-qty").value) || 0;
        const cost = parseFloat(document.getElementById("m-prod-cost").value) || 0;
        const price = parseFloat(document.getElementById("m-prod-price").value) || 0;
        
        if (!brand || !name || isNaN(cost) || isNaN(price)) {
            showToast("Please complete all mandatory fields", "error");
            return;
        }
        
        closeModal();
        
        // Execute Action
        if (isEdit) {
            callPython("update_product", {
                product_id: productId,
                barcode: targetProduct.barcode,
                product_name: name,
                brand: brand,
                category: cat,
                purchase_price: cost,
                selling_price: price,
                quantity: targetProduct.quantity
            }, function(res) {
                if (res.success) {
                    showToast("Product updated successfully");
                    refreshProductsList();
                } else {
                    showToast(res.message, "error");
                }
            });
        } else {
            callPython("add_product", {
                brand: brand,
                product_name: name,
                category: cat,
                purchase_price: cost,
                selling_price: price,
                quantity: qty
            }, function(res) {
                if (res.success) {
                    showToast(`Product registered! Barcode: ${res.barcode}`);
                    refreshProductsList();
                    
                    // Show Barcode Preview immediately
                    setTimeout(() => {
                        previewBarcode(res.barcode, `${brand} ${name}`);
                    }, 500);
                } else {
                    showToast(res.message, "error");
                }
            });
        }
    });
};

window.previewBarcode = function(barcodeVal, fullName) {
    const imgPath = `barcodes/${barcodeVal}.png`;
    const body = `
        <div style="text-align:center; padding:10px;">
            <div style="font-weight:700; font-size:1.15rem; margin-bottom:15px; color:var(--text-main);">${fullName}</div>
            <!-- Dynamic path image container -->
            <div style="background-color:white; padding:15px; border-radius:8px; display:inline-block; margin-bottom:12px; border:2px solid var(--border-color);">
                <img src="../../${imgPath}" alt="Barcode image" style="max-width:100%; height:110px;" onerror="this.src='https://barcode.tec-it.com/barcode.ashx?data='+encodeURIComponent('${barcodeVal}')+'&code=Code128'"/>
            </div>
            <div style="font-family:monospace; font-weight:bold; font-size:1.2rem; color:var(--accent);">${barcodeVal}</div>
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Close</button>
        <button class="btn btn-primary" onclick="closeModal(); printBarcode('${barcodeVal}', '${fullName}', 0)">Print Label</button>
    `;
    openModal("Barcode Scanner Label Preview", body, footer);
};

window.printBarcode = function(barcodeVal, fullName, price) {
    callPython("print_barcode", {
        barcode: barcodeVal,
        product_name: fullName,
        price: price
    }, function(res) {
        if (res.success) {
            showToast("Sticker label sent to printer.");
        } else {
            showToast(res.message, "error");
        }
    });
};

window.regenerateBarcode = function(productId) {
    const p = catalogProducts.find(prod => prod.id === productId);
    if (!p) return;
    
    if (confirm(`Are you sure you want to regenerate a new serial barcode ID for ${p.brand} ${p.product_name}?\nThe old barcode code will become invalid.`)) {
        callPython("regenerate_barcode", { product_id: productId }, function(res) {
            if (res.success) {
                showToast(`New Barcode generated successfully: ${res.barcode}`);
                refreshProductsList();
            } else {
                showToast(res.message, "error");
            }
        });
    }
};

window.deleteProduct = function(productId, fullName) {
    if (confirm(`CAUTION: Are you sure you want to completely delete product ${fullName}?\nThis cannot be undone.`)) {
        callPython("delete_product", { product_id: productId }, function(res) {
            if (res.success) {
                showToast("Product deleted successfully", "warning");
                refreshProductsList();
            } else {
                showToast("Error: " + res.message, "error");
            }
        });
    }
};

// --- 4. CUSTOMERS REGISTRY ---
function initCustomers() {
    // Add customer modal trigger
    document.getElementById("add-customer-modal-btn").addEventListener("click", () => openCustomerFormModal());

    // Reset filters
    document.getElementById("customer-reset-btn").addEventListener("click", () => {
        document.getElementById("customer-search-input").value = "";
        refreshCustomersList();
    });

    // Binds Search
    document.getElementById("customer-search-input").addEventListener("input", function() {
        const query = this.value.trim().toLowerCase();
        filterCustomersTable(query);
    });

    refreshCustomersList();
}

function refreshCustomersList() {
    callPython("get_customers", {}, function(res) {
        if (res.success) {
            customerList = res.customers;
            renderCustomersTable(customerList);
        }
    });
}

function renderCustomersTable(customers) {
    const tbody = document.querySelector("#customers-table tbody");
    tbody.innerHTML = "";

    if (customers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No customers registered</td></tr>`;
        return;
    }

    customers.forEach(c => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td style="font-weight:bold;">${c.customer_name}</td>
            <td>${c.phone || 'N/A'}</td>
            <td>${c.address || 'N/A'}</td>
            <td>${c.created_at ? c.created_at.substring(0, 10) : 'N/A'}</td>
            <td style="text-align:center; display:flex; gap:6px; justify-content:center;">
                <button class="btn btn-secondary btn-icon-only" onclick="viewCustomerLedger(${c.id}, '${c.customer_name}')" title="Purchase Ledger">📋 Ledger</button>
                <button class="btn btn-secondary btn-icon-only" onclick="openCustomerFormModal(${c.id})" title="Edit Profile">✏ Edit</button>
                <button class="btn btn-danger btn-icon-only" onclick="deleteCustomer(${c.id}, '${c.customer_name}')" title="Delete Profile">&times;</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function filterCustomersTable(query) {
    const filtered = customerList.filter(c => 
        c.customer_name.toLowerCase().includes(query) || 
        c.phone.toLowerCase().includes(query) || 
        (c.address && c.address.toLowerCase().includes(query))
    );
    renderCustomersTable(filtered);
}

window.openCustomerFormModal = function(customerId = null) {
    const isEdit = customerId !== null;
    const c = isEdit ? customerList.find(item => item.id === customerId) : null;
    
    const body = `
        <form id="modal-customer-form">
            <div class="form-group">
                <label>Customer Name *</label>
                <input type="text" id="m-cust-name" class="form-control" value="${isEdit ? c.customer_name : ''}" required placeholder="Full Name">
            </div>
            <div class="form-group">
                <label>Phone Number *</label>
                <input type="text" id="m-cust-phone" class="form-control" value="${isEdit ? c.phone : ''}" required placeholder="10-digit primary number">
            </div>
            <div class="form-group">
                <label>Billing Address</label>
                <textarea id="m-cust-addr" class="form-control" rows="3" placeholder="Full residential/office address">${isEdit && c.address ? c.address : ''}</textarea>
            </div>
        </form>
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="m-cust-submit">Save Profile</button>
    `;
    
    openModal(isEdit ? "Edit Customer Profile" : "Register Customer Profile", body, footer);
    
    document.getElementById("m-cust-submit").addEventListener("click", () => {
        const name = document.getElementById("m-cust-name").value.trim();
        const phone = document.getElementById("m-cust-phone").value.trim();
        const addr = document.getElementById("m-cust-addr").value.trim();
        
        if (!name || !phone) {
            showToast("Name and Phone numbers are required", "error");
            return;
        }
        
        closeModal();
        
        if (isEdit) {
            callPython("update_customer", { customer_id: customerId, customer_name: name, phone: phone, address: addr }, function(res) {
                if (res.success) {
                    showToast("Customer profile updated successfully");
                    refreshCustomersList();
                } else {
                    showToast(res.message, "error");
                }
            });
        } else {
            callPython("add_customer", { customer_name: name, phone: phone, address: addr }, function(res) {
                if (res.success) {
                    showToast("Customer profile registered successfully");
                    refreshCustomersList();
                } else {
                    showToast(res.message, "error");
                }
            });
        }
    });
};

window.viewCustomerLedger = function(customerId, customerName) {
    callPython("get_customer_history", { customer_id: customerId }, function(res) {
        if (res.success) {
            let body = `
                <div style="font-weight:700; color:var(--text-main); margin-bottom:8px; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                    Sales Invoices Logs (Double-click to view receipt)
                </div>
                <div class="table-responsive" style="max-height:160px; overflow-y:auto; margin-bottom:20px;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Invoice No</th>
                                <th>Date</th>
                                <th>Method</th>
                                <th>Amount</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            if (res.purchases.length === 0) {
                body += `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No purchases recorded</td></tr>`;
            } else {
                res.purchases.forEach(p => {
                    body += `
                        <tr ondblclick="reprintInvoice('${p.invoice_no}')" style="cursor:pointer;">
                            <td style="font-weight:bold;color:var(--accent);">${p.invoice_no}</td>
                            <td>${p.sale_date.substring(0, 10)}</td>
                            <td>${p.payment_method}</td>
                            <td style="text-align:right;font-weight:bold;">Rs. ${parseFloat(p.total_amount).toFixed(2)}</td>
                        </tr>
                    `;
                });
            }
            
            body += `
                        </tbody>
                    </table>
                </div>
                
                <div style="font-weight:700; color:var(--text-main); margin-bottom:8px; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                    Device Warranties Ledger (1-Year Coverage)
                </div>
                <div class="table-responsive" style="max-height:160px; overflow-y:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>IMEI Code</th>
                                <th>Model Name</th>
                                <th>Coverage Period</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            if (res.warranties.length === 0) {
                body += `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No active hardware warranties</td></tr>`;
            } else {
                res.warranties.forEach(w => {
                    const statusClass = w.status === 'Active' ? 'badge-success' : 'badge-danger';
                    body += `
                        <tr>
                            <td style="font-family:monospace;font-weight:bold;">${w.imei}</td>
                            <td>${w.model}</td>
                            <td style="font-size:0.8rem;">${w.period}</td>
                            <td><span class="badge ${statusClass}">${w.status}</span></td>
                        </tr>
                    `;
                });
            }
            
            body += `
                        </tbody>
                    </table>
                </div>
            `;
            
            const footer = `<button class="btn btn-primary" onclick="closeModal()">Close Ledger</button>`;
            openModal(`Ledger History: ${customerName}`, body, footer);
        } else {
            showToast("Failed to fetch customer ledger", "error");
        }
    });
};

window.reprintInvoice = function(invoiceNo) {
    callPython("reprint_receipt", { invoice_no: invoiceNo });
};

window.deleteCustomer = function(customerId, customerName) {
    if (confirm(`Are you sure you want to delete profile for ${customerName}?\nThis is only possible if they have no checkout logs.`)) {
        callPython("delete_customer", { customer_id: customerId }, function(res) {
            if (res.success) {
                showToast("Customer deleted successfully", "warning");
                refreshCustomersList();
            } else {
                showToast(res.message, "error");
            }
        });
    }
};

// --- 5. STOCK ADJUSTMENTS & IMEIs ---
let activeImeiTab = "available";

function initInventory() {
    // Register IMEI submission
    document.getElementById("imei-register-form").addEventListener("submit", function(e) {
        e.preventDefault();
        const prodId = parseInt(document.getElementById("imei-product-select").value);
        const imeiVal = document.getElementById("imei-code-input").value.trim();
        
        if (!prodId || !imeiVal) {
            showToast("Select model and enter IMEI", "error");
            return;
        }
        
        callPython("add_imei", { product_id: prodId, imei: imeiVal }, function(res) {
            if (res.success) {
                showToast(`IMEI ${imeiVal} registered successfully.`);
                document.getElementById("imei-code-input").value = "";
                document.getElementById("imei-product-select").value = "";
                refreshInventoryLedgers();
            } else {
                showToast(res.message, "error");
            }
        });
    });

    // Scanner helper for adjustments
    document.getElementById("adjust-scan-input").addEventListener("keypress", function(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            const sku = this.value.trim();
            if (!sku) return;
            this.value = "";
            
            const match = catalogProducts.find(p => p.barcode === sku);
            if (match) {
                document.getElementById("adjust-product-select").value = match.id;
                showToast(`Selected: ${match.brand} ${match.product_name}`);
            } else {
                showToast("No product found for barcode: " + sku, "warning");
            }
        }
    });

    // Stock adjustments form submit
    document.getElementById("stock-adjustment-form").addEventListener("submit", function(e) {
        e.preventDefault();
        const prodId = parseInt(document.getElementById("adjust-product-select").value);
        const action = document.getElementById("adjust-action-select").value;
        const qty = parseInt(document.getElementById("adjust-qty-input").value) || 0;
        const reason = document.getElementById("adjust-reason-select").value;
        
        if (!prodId || qty <= 0) {
            showToast("Complete all fields", "error");
            return;
        }
        
        callPython("adjust_stock", { product_id: prodId, type: action, quantity: qty, reason: reason }, function(res) {
            if (res.success) {
                showToast("Stock adjustment logged successfully.");
                document.getElementById("adjust-product-select").value = "";
                document.getElementById("adjust-qty-input").value = "1";
                refreshInventoryLedgers();
            } else {
                showToast(res.message, "error");
            }
        });
    });

    // Binds IMEI filter buttons
    document.getElementById("filter-imei-avail-btn").addEventListener("click", () => setImeiTab("available"));
    document.getElementById("filter-imei-sold-btn").addEventListener("click", () => setImeiTab("sold"));

    refreshInventoryLedgers();
}

function setImeiTab(tabName) {
    activeImeiTab = tabName;
    
    // Toggle active visual states
    const btnAvail = document.getElementById("filter-imei-avail-btn");
    const btnSold = document.getElementById("filter-imei-sold-btn");
    
    if (tabName === "available") {
        btnAvail.style.backgroundColor = "rgba(16,185,129,0.15)";
        btnAvail.style.color = "var(--success)";
        btnSold.style.backgroundColor = "transparent";
        btnSold.style.color = "var(--text-main)";
    } else {
        btnSold.style.backgroundColor = "rgba(239,68,68,0.15)";
        btnSold.style.color = "var(--danger)";
        btnAvail.style.backgroundColor = "transparent";
        btnAvail.style.color = "var(--text-main)";
    }
    
    refreshInventoryLogsTable();
}

function refreshInventoryLedgers() {
    callPython("get_products", {}, function(res) {
        if (res.success) {
            catalogProducts = res.products;
            
            // Populate select dropdowns
            const imeiSelect = document.getElementById("imei-product-select");
            const adjustSelect = document.getElementById("adjust-product-select");
            
            imeiSelect.innerHTML = '<option value="">-- Select Phone Model --</option>';
            adjustSelect.innerHTML = '<option value="">-- Choose Product --</option>';
            
            catalogProducts.forEach(p => {
                adjustSelect.innerHTML += `<option value="${p.id}">${p.brand} ${p.product_name} (${p.barcode})</option>`;
                if (p.category.toLowerCase() === 'phones') {
                    imeiSelect.innerHTML += `<option value="${p.id}">${p.brand} ${p.product_name} (${p.barcode})</option>`;
                }
            });
            
            setImeiTab(activeImeiTab);
        }
    });
}

function refreshInventoryLogsTable() {
    const tbody = document.querySelector("#inventory-logs-table tbody");
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;">Loading audit trails...</td></tr>`;
    
    callPython("get_inventory_logs", { tab: activeImeiTab }, function(res) {
        tbody.innerHTML = "";
        if (res.success && res.logs.length > 0) {
            res.logs.forEach(log => {
                const tr = document.createElement("tr");
                let badgeClass = "badge-info";
                const logType = (log.type || log.status || "").toLowerCase();
                const logDate = log.date || log.added_date || "";
                const logQty = log.quantity !== undefined ? log.quantity : 1;
                const logReason = log.reason || (log.status === 'available' ? 'Available Device' : (log.status === 'sold' ? `Sold via Invoice ${log.sale_id || ''}` : ''));

                if (logType === 'in' || logType === 'sale_cancelled' || logType === 'available') badgeClass = "badge-success";
                if (logType === 'out' || logType === 'sale' || logType === 'sold') badgeClass = "badge-danger";
                
                tr.innerHTML = `
                    <td style="font-size:0.8rem; text-align:center;">${logDate.substring(0, 16)}</td>
                    <td><span style="font-weight:600;">${log.brand}</span> ${log.model}</td>
                    <td style="text-align:center;"><span class="badge ${badgeClass}">${logType}</span></td>
                    <td style="text-align:center; font-weight:bold;">${logQty}</td>
                    <td style="font-size:0.85rem; color:var(--text-muted);">${logReason}</td>
                `;
                
                // Double click IMEI details lookup
                if (activeImeiTab === "sold" || activeImeiTab === "available") {
                    tr.style.cursor = "pointer";
                    tr.addEventListener("dblclick", () => showImeiAuditDetails(log.imei));
                }
                
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No stock log movements recorded</td></tr>`;
        }
    });
}

function showImeiAuditDetails(imeiCode) {
    callPython("get_imei_details", { imei: imeiCode }, function(res) {
        if (res.success && res.details) {
            const d = res.details;
            let info = `
                <p><strong>Phone Model:</strong> ${d.brand} ${d.model}</p>
                <p><strong>Serial IMEI:</strong> <span style="font-family:monospace;font-weight:bold;color:var(--accent);">${d.imei}</span></p>
                <p><strong>Registration Date:</strong> ${d.added_date}</p>
                <p><strong>Status:</strong> <span class="badge ${d.status === 'available' ? 'badge-success' : 'badge-danger'}">${d.status.toUpperCase()}</span></p>
            `;
            if (d.status === 'sold') {
                info += `
                    <div style="border-top:1px solid var(--border-color); margin-top:15px; padding-top:10px;">
                        <p><strong>Invoice No:</strong> <span style="font-weight:bold;color:var(--success);">${d.sale_id}</span></p>
                        <p><strong>Sale Timestamp:</strong> ${d.sale_date}</p>
                        <p><strong>Customer:</strong> ${d.customer_name || 'Walk-in Guest'}</p>
                        <p><strong>Customer Phone:</strong> ${d.customer_phone || 'N/A'}</p>
                    </div>
                `;
            }
            const footer = `<button class="btn btn-primary" onclick="closeModal()">Close</button>`;
            openModal("Device History Audit Lookup", info, footer);
        } else {
            showToast("Failed to fetch IMEI info", "error");
        }
    });
}

// --- 6. PROFIT REPORTS & EXPORTS ---
let reportsActiveRange = "today";

function initReports() {
    // Toggle range selector active states
    const ranges = ["today", "month", "all"];
    ranges.forEach(r => {
        document.getElementById(`report-range-${r}`).addEventListener("click", function() {
            ranges.forEach(range => {
                document.getElementById(`report-range-${range}`).className = "btn btn-secondary";
            });
            this.className = "btn btn-primary";
            reportsActiveRange = r;
            refreshFinancials();
        });
    });

    // Exporters
    document.getElementById("export-sales-btn").addEventListener("click", () => triggerExcelExport("sales"));
    document.getElementById("export-inventory-btn").addEventListener("click", () => triggerExcelExport("inventory"));
    document.getElementById("export-customers-btn").addEventListener("click", () => triggerExcelExport("customers"));

    refreshFinancials();
}

function refreshFinancials() {
    callPython("get_financial_reports", { range: reportsActiveRange }, function(res) {
        if (res.success) {
            const r = res.data;
            document.getElementById("report-gross-revenue").innerText = `Rs. ${parseFloat(r.total_revenue || 0).toFixed(2)}`;
            document.getElementById("report-cogs").innerText = `Rs. ${parseFloat(r.total_cogs || 0).toFixed(2)}`;
            document.getElementById("report-net-profit").innerText = `Rs. ${parseFloat(r.net_profit || 0).toFixed(2)}`;
            
            // Populate Sales Table
            const tbodySales = document.querySelector("#report-sales-table tbody");
            tbodySales.innerHTML = "";
            if (r.invoices.length === 0) {
                tbodySales.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No invoices logged</td></tr>`;
            } else {
                r.invoices.forEach(s => {
                    const tr = document.createElement("tr");
                    tr.style.cursor = "pointer";
                    tr.innerHTML = `
                        <td style="font-weight:bold;color:var(--accent);">${s.invoice}</td>
                        <td style="font-size:0.8rem;text-align:center;">${s.date.substring(0, 16)}</td>
                        <td>${s.customer}</td>
                        <td style="text-align:right;">Rs. ${parseFloat(s.amount).toFixed(2)}</td>
                        <td style="text-align:right;font-weight:bold;color:var(--success);">Rs. ${parseFloat(s.profit).toFixed(2)}</td>
                    `;
                    tr.addEventListener("dblclick", () => reprintInvoice(s.invoice));
                    tbodySales.appendChild(tr);
                });
            }

            // Populate Bestsellers Table
            const tbodyRank = document.querySelector("#report-bestsellers-table tbody");
            tbodyRank.innerHTML = "";
            if (r.bestsellers.length === 0) {
                tbodyRank.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--text-muted);">No sales recorded yet</td></tr>`;
            } else {
                r.bestsellers.forEach(item => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td style="font-weight:bold;">${item.brand} ${item.model}</td>
                        <td style="text-align:center;font-weight:bold;color:var(--accent);">${item.units} sold</td>
                        <td style="text-align:right;font-weight:bold;">Rs. ${parseFloat(item.rev).toFixed(2)}</td>
                    `;
                    tbodyRank.appendChild(tr);
                });
            }
        }
    });
}

function triggerExcelExport(type) {
    callPython("export_excel_report", { type: type }, function(res) {
        if (res.success) {
            showToast(`Report exported successfully!\nPath: ${res.filepath}`);
        } else {
            showToast("Export failed: " + res.message, "error");
        }
    });
}

// --- 7. STORE SETTINGS & USER ACCOUNTS ---
function initSettings() {
    // Populate form data
    callPython("get_settings", {}, function(res) {
        if (res.success) {
            const s = res.settings;
            document.getElementById("settings-shop-name").value = s.shopName || "";
            document.getElementById("settings-shop-phone").value = s.shopPhone || "";
            document.getElementById("settings-shop-email").value = s.shopEmail || "";
            document.getElementById("settings-shop-tax").value = s.taxRate || "18";
            document.getElementById("settings-shop-address").value = s.shopAddress || "";
        }
    });

    // Form submit
    document.getElementById("settings-shop-form").addEventListener("submit", function(e) {
        e.preventDefault();
        const settings = {
            shopName: document.getElementById("settings-shop-name").value.trim(),
            shopPhone: document.getElementById("settings-shop-phone").value.trim(),
            shopEmail: document.getElementById("settings-shop-email").value.trim(),
            taxRate: parseFloat(document.getElementById("settings-shop-tax").value) || 18.0,
            shopAddress: document.getElementById("settings-shop-address").value.trim(),
            printerWidth: "80mm" // keep default
        };
        
        callPython("save_settings", { settings: settings }, function(res) {
            if (res.success) {
                showToast("Store settings saved successfully");
                initSettings(); // Reload settings
            } else {
                showToast("Failed to save settings: " + res.message, "error");
            }
        });
    });

    // Binds Users Action Buttons
    document.getElementById("add-user-btn").addEventListener("click", openRegisterUserModal);
    document.getElementById("delete-user-btn").addEventListener("click", deleteSelectedUserAccount);

    // Binds Backup Buttons
    document.getElementById("backup-export-btn").addEventListener("click", triggerBackupExport);
    document.getElementById("backup-import-btn").addEventListener("click", triggerBackupImport);

    refreshUsersList();
}

function refreshUsersList() {
    const tbody = document.querySelector("#settings-users-table tbody");
    tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;">Loading accounts...</td></tr>`;
    
    callPython("get_users", {}, function(res) {
        tbody.innerHTML = "";
        if (res.success && res.users.length > 0) {
            res.users.forEach(u => {
                const tr = document.createElement("tr");
                tr.setAttribute("data-username", u.username);
                tr.innerHTML = `
                    <td style="font-weight:bold;color:var(--text-main);">${u.username}</td>
                    <td><span class="badge ${u.role === 'admin' ? 'badge-danger' : 'badge-info'}">${u.role.toUpperCase()}</span></td>
                `;
                tr.addEventListener("click", function() {
                    document.querySelectorAll("#settings-users-table tbody tr").forEach(row => row.style.backgroundColor = "transparent");
                    this.style.backgroundColor = "rgba(255,255,255,0.05)";
                    tbody.setAttribute("data-selected-user", u.username);
                });
                tbody.appendChild(tr);
            });
        }
    });
}

function openRegisterUserModal() {
    const body = `
        <div class="form-group">
            <label>Username *</label>
            <input type="text" id="m-reg-username" class="form-control" placeholder="Enter new username" required autocomplete="off">
        </div>
        <div class="form-group">
            <label>Password *</label>
            <input type="password" id="m-reg-password" class="form-control" placeholder="Enter password" required autocomplete="off">
        </div>
        <div class="form-group">
            <label>User Role *</label>
            <select id="m-reg-role" class="form-control">
                <option value="cashier">Cashier Staff</option>
                <option value="admin">Administrator (Full Access)</option>
            </select>
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="m-reg-submit-btn">Create Account</button>
    `;
    openModal("Add User Account", body, footer);
    
    document.getElementById("m-reg-submit-btn").addEventListener("click", () => {
        const username = document.getElementById("m-reg-username").value.trim();
        const password = document.getElementById("m-reg-password").value.trim();
        const role = document.getElementById("m-reg-role").value;
        
        if (!username || !password) {
            showToast("Username and Password are required", "error");
            return;
        }
        
        closeModal();
        
        callPython("add_user", { username: username, password: password, role: role }, function(res) {
            if (res.success) {
                showToast(`User account '${username}' created successfully.`);
                refreshUsersList();
            } else {
                showToast("Failed to create user: " + res.message, "error");
            }
        });
    });
}

function deleteSelectedUserAccount() {
    const selected = document.querySelector("#settings-users-table tbody").getAttribute("data-selected-user");
    if (!selected) {
        showToast("Please select a user account to delete first.", "warning");
        return;
    }
    
    if (selected === 'admin') {
        showToast("The primary 'admin' account cannot be deleted.", "error");
        return;
    }
    
    if (confirm(`Are you sure you want to delete user account '${selected}'?`)) {
        callPython("delete_user", { username: selected }, function(res) {
            if (res.success) {
                showToast(`User account '${selected}' deleted.`, "warning");
                document.querySelector("#settings-users-table tbody").removeAttribute("data-selected-user");
                refreshUsersList();
            } else {
                showToast("Failed to delete user: " + res.message, "error");
            }
        });
    }
}

function triggerBackupExport() {
    callPython("export_backup", {}, function(res) {
        if (res.success) {
            showToast("Database backup file saved successfully.");
        }
    });
}

function triggerBackupImport() {
    if (confirm("WARNING: Restoring database from backup JSON will wipe out all current invoices, inventory counts, and configurations. Proceed?")) {
        callPython("import_backup", {}, function(res) {
            if (res.success) {
                showToast("System database restored successfully! The application will restart now.", "success");
            }
        });
    }
}

// Fallback Mock System for in-browser debug runs
function setupMockBackend() {
    window.backend = {
        execute: function(action, payloadJson, callback) {
            const p = JSON.parse(payloadJson);
            setTimeout(() => {
                if (action === 'login') {
                    if (p.username === 'cashier' && p.password === '123') {
                        callback(JSON.stringify({ success: true, user: { username: 'cashier', role: 'cashier' } }));
                    } else if (p.username === 'admin' && p.password === 'admin123') {
                        callback(JSON.stringify({ success: true, user: { username: 'admin', role: 'admin' } }));
                    } else {
                        callback(JSON.stringify({ success: false, message: "Invalid credentials" }));
                    }
                }
            }, 100);
        }
    };
}

// Binds QWebChannel initialization on window load
window.onload = function() {
    if (typeof qt !== "undefined" && qt.webChannelTransport) {
        new QWebChannel(qt.webChannelTransport, function(channel) {
            window.backend = channel.objects.backend;
            console.log("QWebChannel connected successfully.");
        });
    } else {
        console.warn("Qt WebChannel transport not found. Running mock backend.");
        setupMockBackend();
    }
};

