import type { NextApiRequest, NextApiResponse } from 'next';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import axios from 'axios';

// Disable body parser to handle file uploads and streams
export const config = {
    api: {
        bodyParser: false,
    },
};

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    // Use getServerSession for API routes
    const session = await getServerSession(req, res, authOptions);

    console.log('[Proxy] Session exists:', !!session);
    console.log('[Proxy] AccessToken exists:', !!(session as any)?.accessToken);

    if (!session || !(session as any).accessToken) {
        console.error('[Proxy] No valid session or accessToken');
        return res.status(401).json({ message: 'Unauthorized - no valid session' });
    }

    // Extract story ID and action from the path
    const { params } = req.query;

    if (!params || !Array.isArray(params) || params.length < 1) {
        return res.status(400).json({ message: 'Invalid path' });
    }

    // Join all path segments
    const pathSegments = params.join('/');

    const baseUrl = process.env.API_URL || 'http://localhost:8000';

    // Build full URL including query parameters
    const queryString = Object.entries(req.query)
        .filter(([key]) => key !== 'params')
        .map(([key, val]) => `${key}=${encodeURIComponent(String(val))}`)
        .join('&');

    const endpoint = `${baseUrl}/api/v1/stories/${pathSegments}${queryString ? `?${queryString}` : ''}`;

    console.log('[Proxy] Calling:', req.method, endpoint);

    try {
        const response = await axios({
            method: req.method as string,
            url: endpoint,
            data: req, // Stream the request directly
            headers: {
                'Authorization': `Bearer ${(session as any).accessToken}`,
                'Content-Type': req.headers['content-type'] || 'application/json', // Forward content type (essential for multipart)
            },
            timeout: 90000,
            responseType: 'stream', // Important to handle response streams similarly if needed
        });

        console.log('[Proxy] Success:', response.status);

        // Forward response headers
        Object.entries(response.headers).forEach(([key, value]) => {
            res.setHeader(key, value as string);
        });

        // Pipe response data
        response.data.pipe(res);

    } catch (error: any) {
        console.error('[Proxy] Error:', error.response?.status, error.message);

        if (error.response) {
            res.status(error.response.status);
            // If response is a stream, pipe it
            if (error.response.data && typeof error.response.data.pipe === 'function') {
                error.response.data.pipe(res);
            } else {
                res.json(error.response.data);
            }
        } else {
            res.status(500).json({
                error: error.message,
                detail: 'An error occurred',
            });
        }
    }
}
