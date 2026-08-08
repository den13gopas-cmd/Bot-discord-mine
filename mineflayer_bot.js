const mineflayer = require('mineflayer');

const config = {
  host: process.env.MC_SERVER_IP || '127.0.0.1',
  port: Number(process.env.MC_SERVER_PORT || 25565),
  username: process.env.MC_CLIENT_USERNAME || 'BotMineflayer',
  password: process.env.MC_CLIENT_PASSWORD || '',
  version: process.env.MC_CLIENT_VERSION || '1.21.8',
};

if (!config.username) {
  console.log('MC_CLIENT_USERNAME is not set; skipping Mineflayer client startup.');
  process.exit(0);
}

const bot = mineflayer.createBot({
  host: config.host,
  port: config.port,
  username: config.username,
  password: config.password || undefined,
  version: config.version,
  auth: config.password ? 'microsoft' : 'offline',
  hideErrors: false,
});

bot.on('spawn', () => {
  console.log(`[Mineflayer] Connected as ${bot.username}`);
  bot.chat('/register ' + (process.env.MC_CLIENT_REGISTER_PASSWORD || '12345678'));
  bot.chat('/login ' + (process.env.MC_CLIENT_LOGIN_PASSWORD || '12345678'));
});

bot.on('message', (msg) => {
  console.log(`[Mineflayer] ${msg}`);
});

bot.on('kicked', (reason) => {
  console.log(`[Mineflayer] Kicked: ${reason}`);
});

bot.on('error', (err) => {
  console.log(`[Mineflayer] Error: ${err}`);
});

bot.on('end', (reason) => {
  console.log(`[Mineflayer] Disconnected: ${reason}`);
});
