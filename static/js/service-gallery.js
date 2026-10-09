(() => {
  const gallery = document.querySelector('[data-service-gallery]');
  if (!gallery) return;
  const main = gallery.querySelector('[data-service-gallery-main]'); const image = gallery.querySelector('[data-service-gallery-image]'); const thumbs = Array.from(gallery.querySelectorAll('[data-service-gallery-thumb]'));
  if (!main || !image || !thumbs.length) return;
  const lightbox = document.querySelector('[data-service-lightbox]'); const lightboxImage = lightbox?.querySelector('[data-service-lightbox-image]'); const counter = lightbox?.querySelector('[data-service-lightbox-counter]'); const lightboxContent = lightbox?.querySelector('.gallery-lightbox-content'); let touchStart = null; let lightboxTouchStart = null;
  let current = 0;
  const setImage = (index) => { current = (index + thumbs.length) % thumbs.length; const thumb = thumbs[current]; image.src = thumb.dataset.imageUrl; image.alt = thumb.dataset.imageAlt; thumbs.forEach((item, i) => { const active = i === current; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); }); if (lightboxImage) { lightboxImage.src = thumb.dataset.imageUrl; lightboxImage.alt = thumb.dataset.imageAlt; } if (counter) counter.textContent = `${current + 1} / ${thumbs.length}`; };
  const next = () => setImage(current + 1); const previous = () => setImage(current - 1);
  const openLightbox = () => { if (!lightbox) return; setImage(current); lightbox.hidden = false; document.body.classList.add('gallery-lightbox-open', 'lightbox-open'); lightboxContent?.focus(); };
  const closeLightbox = () => { if (!lightbox) return; lightbox.hidden = true; document.body.classList.remove('gallery-lightbox-open', 'lightbox-open'); main.focus(); };
  gallery.querySelector('[data-service-gallery-next]')?.addEventListener('click', next); gallery.querySelector('[data-service-gallery-prev]')?.addEventListener('click', previous); gallery.querySelector('[data-service-gallery-thumbs]')?.addEventListener('click', event => { const thumb = event.target.closest('[data-service-gallery-thumb]'); if (thumb) setImage(thumbs.indexOf(thumb)); });
  main.addEventListener('click', event => { if (!event.target.closest('button')) openLightbox(); }); main.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openLightbox(); } });
  lightbox?.querySelector('[data-service-lightbox-next]')?.addEventListener('click', next); lightbox?.querySelector('[data-service-lightbox-prev]')?.addEventListener('click', previous); lightbox?.querySelectorAll('[data-service-lightbox-close]').forEach(item => item.addEventListener('click', closeLightbox));
  if (lightbox && thumbs.length < 2) { lightbox.querySelector('[data-service-lightbox-prev]').hidden = true; lightbox.querySelector('[data-service-lightbox-next]').hidden = true; if (counter) counter.hidden = true; }
  gallery.addEventListener('touchstart', event => { touchStart = event.changedTouches[0].clientX; }, {passive: true}); gallery.addEventListener('touchend', event => { if (touchStart === null || thumbs.length < 2) return; const distance = event.changedTouches[0].clientX - touchStart; if (Math.abs(distance) > 45) distance < 0 ? next() : previous(); touchStart = null; });
  lightbox?.addEventListener('touchstart', event => { lightboxTouchStart = event.changedTouches[0].clientX; }, {passive: true}); lightbox?.addEventListener('touchend', event => { if (lightboxTouchStart === null || thumbs.length < 2) return; const distance = event.changedTouches[0].clientX - lightboxTouchStart; if (Math.abs(distance) > 45) distance < 0 ? next() : previous(); lightboxTouchStart = null; }, {passive: true});
  document.addEventListener('keydown', event => { if (!lightbox || lightbox.hidden) return; if (event.key === 'Escape') closeLightbox(); if (event.key === 'ArrowRight') next(); if (event.key === 'ArrowLeft') previous(); });
  setImage(0);
})();
