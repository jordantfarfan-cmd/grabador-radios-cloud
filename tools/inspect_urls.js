// Sandbox: Scraper to extract streaming links from target pages
async function inspect() {
    const urls = [
        { name: 'Oxigeno', url: 'https://audioplayer.pe/oxigeno' },
        { name: 'Studio92', url: 'https://audioplayer.pe/studio92' },
        { name: 'Moda', url: 'https://www.oigo.com/moda/radioenvivo/' },
        { name: 'Planeta', url: 'https://www.oigo.com/planeta/radioenvivo/' },
        { name: 'OndaCero', url: 'https://www.ondacero.com.pe/radio/' },
        { name: 'Panamericana', url: 'https://www.radiopanamericana.com/radio/' }
    ];

    for (const item of urls) {
        try {
            console.log(`\nFetching ${item.name} (${item.url})...`);
            const res = await fetch(item.url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            });
            const text = await res.text();
            
            // Search for mdstrm, streaming urls, m3u8, audio endpoints
            const matches = text.match(/https?:\/\/[^"'\s\\]+(?:mdstrm\.com|streamtheworld|icecast|\.m3u8|\.aac)[^"'\s\\]*/gi) || [];
            const unique = [...new Set(matches)];
            console.log(`Found ${unique.length} potential stream URLs for ${item.name}:`);
            unique.forEach(u => console.log('  ->', u));

            // Also check for media ID patterns (e.g., 24-character hex strings in Mediastream)
            const idMatches = text.match(/(?:audio|live|media)[\/:]([a-f0-9]{24})/gi) || [];
            if (idMatches.length > 0) {
                console.log(`Found IDs for ${item.name}:`, [...new Set(idMatches)]);
            }
        } catch (e) {
            console.log(`Error fetching ${item.name}: ${e.message}`);
        }
    }
}

inspect();
