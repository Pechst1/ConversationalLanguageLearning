import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ message: 'Method not allowed' });
    }

    try {
        // Forward the request to AnkiConnect
        // We explicitly set the Origin to http://localhost to satisfy AnkiConnect's CORS check
        // even if the request comes from a different port or origin.
        const response = await axios.post('http://127.0.0.1:8765', req.body, {
            headers: {
                'Origin': 'http://localhost',
                'Content-Type': 'application/json'
            }
        });

        res.status(200).json(response.data);
    } catch (error: any) {
        console.error('Anki proxy error:', error.message);
        res.status(error.response?.status || 500).json({
            error: error.message,
            details: error.response?.data
        });
    }
}
