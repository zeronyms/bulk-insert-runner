(function() {
    // Only init once
    if (window.__spatialGlassInitialized) return;
    window.__spatialGlassInitialized = true;

    // Track mouse coordinates across the document for light reflections
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let targetX = mouseX;
    let targetY = mouseY;
    let rafId = null;

    function onMouseMove(e) {
        targetX = e.clientX;
        targetY = e.clientY;
        if (!rafId) {
            rafId = requestAnimationFrame(updateLight);
        }
    }

    function onDeviceOrientation(e) {
        if (e.gamma !== null && e.beta !== null) {
            const normX = Math.min(Math.max((e.gamma + 45) / 90, 0), 1);
            const normY = Math.min(Math.max((e.beta + 45) / 90, 0), 1);
            targetX = normX * window.innerWidth;
            targetY = normY * window.innerHeight;
            if (!rafId) {
                rafId = requestAnimationFrame(updateLight);
            }
        }
    }

    function updateLight() {
        // Smooth lerp for specular light reflections (NO physical tilting of layout cards)
        mouseX += (targetX - mouseX) * 0.2;
        mouseY += (targetY - mouseY) * 0.2;

        const root = document.documentElement;
        root.style.setProperty('--cursor-x', `${mouseX.toFixed(1)}px`);
        root.style.setProperty('--cursor-y', `${mouseY.toFixed(1)}px`);

        // Update relative specular reflection coords only for elements in viewport
        const glassElements = document.querySelectorAll(
            '.workbench-panel, .spec-card, .target-inspector, .sidebar-status-box, .pipeline-bar, .app-masthead, [data-testid="stExpander"]'
        );

        glassElements.forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.bottom >= 0 && rect.top <= window.innerHeight && rect.right >= 0 && rect.left <= window.innerWidth) {
                const relX = mouseX - rect.left;
                const relY = mouseY - rect.top;
                el.style.setProperty('--card-x', `${relX.toFixed(1)}px`);
                el.style.setProperty('--card-y', `${relY.toFixed(1)}px`);
            }
        });

        if (Math.abs(targetX - mouseX) > 0.5 || Math.abs(targetY - mouseY) > 0.5) {
            rafId = requestAnimationFrame(updateLight);
        } else {
            rafId = null;
        }
    }

    // Attach listeners
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    window.addEventListener('touchmove', (e) => {
        if (e.touches && e.touches[0]) {
            targetX = e.touches[0].clientX;
            targetY = e.touches[0].clientY;
            if (!rafId) rafId = requestAnimationFrame(updateLight);
        }
    }, { passive: true });

    if (window.DeviceOrientationEvent) {
        window.addEventListener('deviceorientation', onDeviceOrientation, { passive: true });
    }

    // Initial trigger
    updateLight();
})();
