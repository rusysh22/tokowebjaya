/* ===== Toko Web Jaya — Main JS ===== */

// Scroll reveal animation
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        // Stagger children if data-stagger attribute present
        const children = entry.target.querySelectorAll("[data-reveal-child]");
        children.forEach((child, i) => {
          setTimeout(() => child.classList.add("revealed"), i * 100);
        });
      }
    });
  },
  { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
);

document.querySelectorAll(".reveal").forEach((el) => revealObserver.observe(el));

// Navbar scroll effect
const navbar = document.getElementById("navbar");
if (navbar) {
  window.addEventListener("scroll", () => {
    if (window.scrollY > 20) {
      navbar.classList.add("shadow-lg");
    } else {
      navbar.classList.remove("shadow-lg");
    }
  });
}

// Product card 3D tilt effect
document.querySelectorAll("[data-tilt]").forEach((card) => {
  card.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((y - centerY) / centerY) * -6;
    const rotateY = ((x - centerX) / centerX) * 6;
    card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(4px)`;
  });

  card.addEventListener("mouseleave", () => {
    card.style.transform = "perspective(800px) rotateX(0) rotateY(0) translateZ(0)";
    card.style.transition = "transform 0.4s ease";
  });

  card.addEventListener("mouseenter", () => {
    card.style.transition = "transform 0.1s ease";
  });
});

// Smooth counter animation
function animateCounter(el) {
  const target = parseInt(el.dataset.target, 10);
  const duration = 1500;
  const start = performance.now();
  const update = (time) => {
    const elapsed = time - start;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.floor(ease * target).toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

const counterObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting && !entry.target.dataset.animated) {
        entry.target.dataset.animated = "true";
        animateCounter(entry.target);
      }
    });
  },
  { threshold: 0.5 }
);

document.querySelectorAll("[data-counter]").forEach((el) => counterObserver.observe(el));

// Toast notification
window.showToast = function (message, type = "success") {
  const toast = document.createElement("div");
  const colors = {
    success: "bg-neon text-black",
    error: "bg-red-600 text-white",
    info: "bg-gray-800 text-white border border-gray-700",
  };
  toast.className = `fixed bottom-6 right-6 z-[9999] px-5 py-3 text-sm font-semibold shadow-2xl transition-all duration-300 translate-y-4 opacity-0 ${colors[type] || colors.info}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-4", "opacity-0");
  });
  setTimeout(() => {
    toast.classList.add("translate-y-4", "opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
};

// Pricing toggle (OTF vs Subscription)
const pricingToggle = document.getElementById("pricing-toggle");
if (pricingToggle) {
  pricingToggle.addEventListener("change", () => {
    document.querySelectorAll("[data-price-otf]").forEach((el) => {
      el.style.display = pricingToggle.checked ? "none" : "block";
    });
    document.querySelectorAll("[data-price-sub]").forEach((el) => {
      el.style.display = pricingToggle.checked ? "block" : "none";
    });
  });
}

// Video lazy load
document.querySelectorAll("video[data-src]").forEach((video) => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        video.src = video.dataset.src;
        video.load();
        observer.disconnect();
      }
    });
  });
  observer.observe(video);
});
