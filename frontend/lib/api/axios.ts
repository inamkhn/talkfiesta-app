import axios from 'axios';

// Ensure we are in the browser before accessing localStorage
const isBrowser = typeof window !== 'undefined';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach the token to outgoing requests
apiClient.interceptors.request.use(
  (config) => {
    if (isBrowser) {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Prevent multiple simultaneous refresh requests
let isRefreshing = false;
let failedQueue: Array<{ resolve: (value?: unknown) => void; reject: (reason?: any) => void }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response Interceptor: Catch 401s and automatically refresh the token
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If it's a 401 Unauthorized and we haven't already retried this request
    if (error.response?.status === 401 && !originalRequest._retry) {
      
      if (isRefreshing) {
        // If we are already refreshing, queue this request to wait
        return new Promise(function (resolve, reject) {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = 'Bearer ' + token;
            return apiClient(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = isBrowser ? localStorage.getItem('refresh_token') : null;
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        // Call the backend /refresh endpoint directly using raw axios 
        // to prevent infinite loops if the refresh itself returns 401
        const response = await axios.post(
          `${apiClient.defaults.baseURL}/auth/refresh`,
          { refresh_token: refreshToken }
        );

        const { access_token, refresh_token: new_refresh_token } = response.data;

        if (isBrowser) {
          localStorage.setItem('access_token', access_token);
          if (new_refresh_token) {
              localStorage.setItem('refresh_token', new_refresh_token);
          }
        }

        apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        
        processQueue(null, access_token);
        
        // Retry the original failed request
        return apiClient(originalRequest);
        
      } catch (refreshError) {
        processQueue(refreshError, null);
        
        // If refreshing the token completely fails (e.g., refresh token expired)
        // We log the user out and redirect to login
        if (isBrowser) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);


export default apiClient;
