
() => {
    function parseFontSize(s) {
        return parseInt(s.replace(/[px]/g, ''))
    };

    function getCssSelector(el) {
        let path = [], parent;
        while (parent = el.parentNode) {
            path.unshift(el.tagName);
            el = parent;
        }
        return `${path.join(' > ')}`.toLowerCase();
    };

    function replaceNbsps(str) {
        return str.replace(new RegExp(String.fromCharCode(160), "g"), " ");  // remove \xa0
    }

    function splitIntoWords(str) {
        return str.split(/[\r\n\s]+/).filter(s => s.length > 0);
    }

    try {
        links = [];
        pos = 0;
        // remove elements that are not visible
        let elements = document.body.getElementsByTagName("*");
        for (let i = 0; i < elements.length; i++) {
            let style = window.getComputedStyle(elements[i]);
            if (style.display === "none" ||
                style.visibility === "hidden" ||
                style.opacity === "0" ||
                style.opacity === "0.0") {
                elements[i].parentNode.removeChild(elements[i]);
            } else if (elements[i].tagName === "A") {
                // extract links
                let text = elements[i].innerText.trim();
                let href = elements[i].getAttribute("href");
                if (text && href) {
                    let parentStyle = window.getComputedStyle(elements[i].parentNode);
                    let link = {
                        "pos": pos,
                        "cssSel": getCssSelector(elements[i]),
                        "text": replaceNbsps(text),
                        "href": href,
                        "url": new URL(href, document.location).href,
                        "fontSize": parseFontSize(style.fontSize),  // e.g. "12px" -> 12
                        "fontWeight": parseInt(style.fontWeight),  // e.g. "400" -> 400
                        "color": style.color,  // e.g. "rgb(51, 51, 51)"
                        "font": style.font,
                        "parentPadding": parentStyle.padding,
                        "parentMargin": parentStyle.margin,
                        "parentBgColor": parentStyle.backgroundColor,
                    };
                    link["words"] = splitIntoWords(link.text);
                    links.push(link);
                }
                pos += 1;
            }
        }
        return links;
    } catch(err) {
        return { err: [err.toString()] };
    }
}
