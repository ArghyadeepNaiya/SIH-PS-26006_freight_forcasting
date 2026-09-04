// Express gateway. Single door into the system so every request is logged in one place.
import express from 'express';
import cors from 'cors';
import morgan from 'morgan';
import axios from 'axios';

const app = express();
const ML = process.env.ML_URL || 'http://localhost:8000';
app.use(cors()); app.use(express.json()); app.use(morgan('dev'));

const proxy = (path, method = 'get') => async (req, res) => {
  try {
    const r = method === 'post'
      ? await axios.post(`${ML}${path}`, req.body)
      : await axios.get(`${ML}${path}`, { params: req.query });
    res.json(r.data);
  } catch (e) {
    res.status(e.response?.status || 500).json(e.response?.data || { error: e.message });
  }
};

app.post('/api/recommend', proxy('/ml/recommend', 'post'));
app.get('/api/forecast',   proxy('/ml/forecast'));
app.get('/api/history',    proxy('/ml/history'));
app.get('/api/skill',      proxy('/ml/skill'));
app.get('/api/reference',  proxy('/ml/reference'));
app.get('/api/health',     proxy('/ml/health'));

const scenarios = [];   // swap for MongoDB in Phase 1
app.post('/api/scenarios', (req, res) => {
  scenarios.push({ id: scenarios.length + 1, savedAt: new Date(), ...req.body });
  res.json(scenarios.at(-1));
});
app.get('/api/scenarios', (_, res) => res.json(scenarios));

app.listen(process.env.PORT || 4000, () =>
  console.log(`Gateway on ${process.env.PORT || 4000}, ML at ${ML}`));
