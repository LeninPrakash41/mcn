import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { MCNProvider } from './services/mcn-client';

import HomePage from './pages/HomePage';
import AdminPage from './pages/AdminPage';

export function AppRouter() {
    return (
        <MCNProvider endpoint="http://localhost:8000">
            <Router>
                <Routes>
                    <Route path="/" element={<HomePage />} />
<Route path="/admin" element={<AdminPage />} />
                    <Route path="*" element={<div>Page not found</div>} />
                </Routes>
            </Router>
        </MCNProvider>
    );
}

export default AppRouter;
