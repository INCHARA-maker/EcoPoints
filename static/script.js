
const ecoQuotes = [
    "Small actions create a greener future. Start with one device.",
    "Your old electronics can become tomorrow's new opportunities.",
    "Be part of the solution. Make recycling your habit.",
    "The planet does not need a few perfect people. It needs more people taking action.",
    "Every responsible recycling decision matters.",
    "Don't let your old technology become tomorrow's problem.",
    "A better future begins with the choices we make today."
];

function newQuote() {
    const quote = document.getElementById("ecoQuote");

    if (!quote) return;

    let nextQuote;

    do {
        nextQuote =
            ecoQuotes[Math.floor(Math.random() * ecoQuotes.length)];
    } while (nextQuote === quote.textContent);

    quote.style.opacity = 0;

    setTimeout(() => {
        quote.textContent = nextQuote;
        quote.style.opacity = 1;
    }, 200);
}
