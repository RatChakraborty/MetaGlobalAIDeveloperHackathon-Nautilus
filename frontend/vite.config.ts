import { defineConfig } from 'vite';
export default defineConfig({server:{allowedHosts:['terminal.local']},base: process.env.NAUTILUS_BASE || './',build:{target:'es2022'}});
