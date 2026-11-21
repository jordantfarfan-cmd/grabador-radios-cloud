import { exec } from 'child_process';
import util from 'util';

const execPromise = util.promisify(exec);

const ALL_STATIONS = [
    { name: 'MODA', url: 'https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/icecast.audio' },
    { name: 'PLANETA', url: 'https://mdstrm.com/audio/6839e274f40e6b9832e37633/icecast.audio' },
    { name: 'ONDA CERO', url: 'https://mdstrm.com/audio/6598b65ab398c90871aff8cc/icecast.audio' },
    { name: 'PANAMERICANA', url: 'https://mdstrm.com/audio/6598b62dded1380470f4e539/icecast.audio' },
    { name: 'STUDIO 92', url: 'https://mdstrm.com/audio/5fada553978fe1080e3ac5ea/icecast.audio' },
    { name: 'LA ZONA', url: 'https://mdstrm.com/audio/5fada54116646e098d97e6a5/icecast.audio' },
    { name: 'OXIGENO', url: 'https://mdstrm.com/audio/5fab0687bcd6c2389ee9480c/icecast.audio' },
    { name: 'VIVA FM', url: 'https://tupanel.info:8780/stream' }
];

async function verifyAll() {
    console.log("=== VERIFICANDO LAS 8 EMISORAS DE RADIO CON FFPROBE ===\n");
    let passed = 0;
    for (const st of ALL_STATIONS) {
        process.stdout.write(`Probando ${st.name.padEnd(15)} ... `);
        try {
            const cmd = `ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels,bit_rate -of json "${st.url}"`;
            const { stdout } = await execPromise(cmd, { timeout: 10000 });
            const data = JSON.parse(stdout);
            const stream = data.streams?.[0];
            if (stream) {
                console.log(`[OK] Codec: ${stream.codec_name}, ${stream.sample_rate}Hz, ${stream.channels}ch, ${Math.round(stream.bit_rate/1000 || 128)}kbps`);
                passed++;
            } else {
                console.log(`[SIN STREAM] Respuesta vacía`);
            }
        } catch (e) {
            console.log(`[FALLO] ${e.message.split('\n')[0]}`);
        }
    }
    console.log(`\nResultado: ${passed} de ${ALL_STATIONS.length} radios funcionando al 100%.`);
}

verifyAll();
