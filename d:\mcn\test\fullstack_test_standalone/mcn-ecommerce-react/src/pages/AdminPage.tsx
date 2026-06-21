import React, { useState, useEffect, useCallback } from 'react';
import { useMCN } from '../services/mcn-client';
import { UIButton, UIInput, UIText, UIContainer, UIForm, UITable, UIChart } from '../components/UIComponents';

interface PageData {
    [key: string]: any;
}

interface ApiResponse {
    success: boolean;
    data?: PageData;
    error?: string;
}

export function AdminPage() {
    const mcn = useMCN();
    const [data, setData] = useState<PageData>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const loadPageData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            
            const result: ApiResponse = await mcn.call('load_page_data', { page: 'Admin' });
            
            if (result?.success && result.data) {
                setData(result.data);
            } else {
                throw new Error(result?.error || 'Failed to load data');
            }
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to load page data';
            setError(errorMessage);
            console.error('Error loading page data:', err);
        } finally {
            setLoading(false);
        }
    }, [mcn]);
    
    useEffect(() => {
        loadPageData();
    }, [loadPageData]);
    
    const handleRefresh = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            
            const result: ApiResponse = await mcn.call('refresh_dashboard', {});
            
            if (result?.success && result.data) {
                setData(result.data);
            } else {
                throw new Error(result?.error || 'Failed to refresh data');
            }
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to refresh data';
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    }, [mcn]);
    
    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen" role="status" aria-label="Loading">
                <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500" aria-hidden="true"></div>
                <span className="sr-only">Loading...</span>
            </div>
        );
    }
    
    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen" role="alert">
                <div className="text-red-500 text-center max-w-md">
                    <h2 className="text-xl font-bold mb-2">Error</h2>
                    <p className="mb-4">{error}</p>
                    <button 
                        onClick={handleRefresh}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        type="button"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }
    
    return (
        <div className="page page-admin min-h-screen bg-gray-50">
            
            <UIContainer className="admin-dashboard">
                
            <UIText 
                content="Admin Dashboard"
                tag="h1"
                className="text"
            />
            <UIChart 
                type="line"
                data={data.analytics_data || []}
                className="chart"
            />
            </UIContainer>
        </div>
    );
}

export default AdminPage;
