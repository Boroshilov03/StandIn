import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BUREAU_URL = 'http://localhost:8000';

function agentProxy(agentAddress) {
  return {
    target: BUREAU_URL,
    changeOrigin: false,
    rewrite: (path) => path.replace(/^\/api\/(?:perform|status|history)/, ''),
    headers: {
      'x-uagents-address': agentAddress,
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/perform': agentProxy('agent1qf83fffdv22j2etuqarww9nwqcenq5zavvekh7k2utflqaxx08j4x38e69v'),
      '/api/status': agentProxy('agent1q2l8xf3dvwvmarl2dpxwtv5ym7pvge53szhstykukmrwuhm93z6k68tphgh'),
      '/api/history': agentProxy('agent1qf60yzmr9reyjnduq8qneum5nf03zzaw60cl6yny9l7la676unf7jdfdtrv'),
    },
  },
});
