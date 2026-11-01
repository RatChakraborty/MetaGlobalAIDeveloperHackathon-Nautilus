import { defineConfig } from 'vite';
export default defineConfig({server:{allowedHosts:['terminal.local']},base: process.env.NAUTILUS_BASE || './',define:{__NAUTILUS_DEMO_ENABLED__:process.env.NAUTILUS_DEMO_ENABLED==='true',__NAUTILUS_BASE__:JSON.stringify(process.env.NAUTILUS_BASE || './')},build:{target:'es2022'}});
