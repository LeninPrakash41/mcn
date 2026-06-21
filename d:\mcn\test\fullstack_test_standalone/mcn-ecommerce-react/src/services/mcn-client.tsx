import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import axios, { AxiosError } from 'axios';

interface MCNContextType {
    endpoint: string;
    call: (action: string, data?: any) => Promise<any>;
    loading: boolean;
    error: string | null;
}

const MCNContext = createContext<MCNContextType | null>(null);

export function MCNProvider({ children, endpoint }: { children: React.ReactNode, endpoint: string }) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    const call = useCallback(async (action: string, data: any = {}) => {
        if (!action?.trim()) {
            throw new Error('Action is required');
        }
        
        setLoading(true);
        setError(null);
        
        try {
            const response = await axios.post(`${endpoint}/api/main`, {
                action: action.trim(),
                ...data
            }, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: 30000,
                validateStatus: (status) => status < 500
            });
            
            if (response.status >= 400) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response.data;
        } catch (err) {
            let errorMessage = 'Network error occurred';
            
            if (err instanceof AxiosError) {
                errorMessage = err.response?.data?.error || 
                              err.response?.data?.message || 
                              err.message || 
                              'Request failed';
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setLoading(false);
        }
    }, [endpoint]);
    
    const contextValue = useMemo(() => ({
        endpoint,
        call,
        loading,
        error
    }), [endpoint, call, loading, error]);
    
    return (
        <MCNContext.Provider value={contextValue}>
            {children}
        </MCNContext.Provider>
    );
}

export function useMCN() {
    const context = useContext(MCNContext);
    if (!context) {
        throw new Error('useMCN must be used within MCNProvider');
    }
    return context;
}

export default MCNProvider;
