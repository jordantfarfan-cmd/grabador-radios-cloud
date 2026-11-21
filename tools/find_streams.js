// Sandbox: Script to discover and test Peruvian radio stream URLs
import https from 'https';

const query = async (url) => {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    resolve([]);
                }
            });
        }).on('error', reject);
    });
};

async function main() {
    console.log("Searching radio-browser.info for Peru stations...");
    const stations = await query('https://de1.api.radio-browser.info/json/stations/bycountry/Peru');
    
    const targets = [
        'Moda', 'Onda Cero', 'Studio 92', 'Oxigeno', 'La Zona', 'Planeta', 'Panamericana', 'Viva'
    ];

    const results = [];
    for (const station of stations) {
        for (const target of targets) {
            if (station.name && station.name.toLowerCase().includes(target.toLowerCase())) {
                results.push({
                    target,
                    name: station.name,
                    url: station.url_resolved || station.url,
                    codec: station.codec,
                    bitrate: station.bitrate
                });
            }
        }
    }

    console.log(`Found ${results.length} matching stations:`);
    console.log(JSON.stringify(results, null, 2));
}

main().catch(console.error);
