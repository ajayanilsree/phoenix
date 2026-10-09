(() => {
  const links = document.querySelectorAll('a[data-service-preview]');
  let card;
  let requestId = 0;
  const removeCard = () => { if (card) { card.remove(); card = null; } };
  const close = () => { requestId += 1; removeCard(); };
  const show = async (link) => {
    const currentRequestId = ++requestId;
    removeCard();
    const url = link.href;
    let data = {title: link.textContent.trim(), domain: new URL(url).hostname};
    try { const response = await fetch(`/services/link-preview/?url=${encodeURIComponent(url)}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}}); if (response.ok) data = {...data, ...(await response.json())}; } catch (_) {}
    if (currentRequestId !== requestId || (!link.matches(':hover') && document.activeElement !== link)) return;
    removeCard();
    card = document.createElement('aside'); card.className = 'service-link-preview';
    if (data.image_url) { const image = document.createElement('img'); image.src = data.image_url; image.alt = ''; card.append(image); }
    const content = document.createElement('div'); const title = document.createElement('strong'); title.textContent = data.title || data.domain; content.append(title); if (data.domain) { const domain = document.createElement('small'); domain.textContent = data.domain; content.append(domain); } if (data.description) { const description = document.createElement('p'); description.textContent = data.description; content.append(description); } card.append(content); document.body.append(card);
    const rect = link.getBoundingClientRect(); const left = Math.min(Math.max(8, rect.left), window.innerWidth - card.offsetWidth - 8); card.style.left = `${left}px`; card.style.top = `${Math.min(window.innerHeight - card.offsetHeight - 8, rect.bottom + 8)}px`;
  };
  links.forEach(link => { link.addEventListener('mouseenter', () => show(link)); link.addEventListener('focus', () => show(link)); link.addEventListener('mouseleave', close); link.addEventListener('blur', close); });
})();
