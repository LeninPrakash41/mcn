import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { MCNProvider } from './services/mcn-client';

import TestPagePage from './pages/TestPagePage';

export function AppRouter() {
    return (
        <MCNProvider endpoint="http://localhost:8000">
            <Router>
                <Routes>
                    <Route path="/test" element={<TestPagePage />} />
                    <Route path="*" element={<div>Page not found</div>} />
                </Routes>
            </Router>
        </MCNProvider>
    );
}

export default AppRouter;
