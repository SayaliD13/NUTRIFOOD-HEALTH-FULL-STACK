const drawer = document.getElementById('side-drawer');
const overlay = document.getElementById('drawer-overlay');
const openBtn = document.getElementById('menu-toggle-btn');
const closeBtn = document.getElementById('drawer-close-btn');

function openDrawer() {
    drawer.classList.add('open');
    overlay.classList.add('show');
}

function closeDrawer() {
    drawer.classList.remove('open');
    overlay.classList.remove('show');
}

if (openBtn) openBtn.onclick = openDrawer;
if (closeBtn) closeBtn.onclick = closeDrawer;
if (overlay) overlay.onclick = closeDrawer;
