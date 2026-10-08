const searchInput = document.getElementById('feature-search-input');
const featureCards = document.querySelectorAll('.feature-card');

if (searchInput) {
    searchInput.addEventListener('input', function () {
        const typedText = searchInput.value.toLowerCase();

        featureCards.forEach(card => {
            const cardName = card.dataset.name.toLowerCase();
            if (cardName.includes(typedText)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    });
}
