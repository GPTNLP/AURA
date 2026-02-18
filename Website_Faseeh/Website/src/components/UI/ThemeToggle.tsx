export default function ThemeToggle() {
    const cycle = () => {
        const html = document.documentElement;
        const current = html.getAttribute("data-theme") || "tamu";

        const next =
            current === "tamu" ? "robotic" :
            current === "robotic" ? "dark" :
            "tamu";

        html.setAttribute("data-theme", next);
        console.log("Theme switched to:", next);
    };

    return (
        <button onClick={cycle} style={{ position: "absolute", bottom: 20, right: 20 }}>
            Theme
        </button>
    );
}
