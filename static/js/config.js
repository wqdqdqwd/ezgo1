// Configuration loader for EzyagoTrading frontend
class ConfigLoader {
    constructor() {
        this.firebaseConfig = null;
        this.isLoaded = false;
    }

    async loadFirebaseConfig() {
        if (this.isLoaded && this.firebaseConfig) {
            return this.firebaseConfig;
        }

        try {
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.firebaseConfig = await response.json();
            this.isLoaded = true;
            
            console.log('Firebase config loaded from backend');
            return this.firebaseConfig;
            
        } catch (error) {
            console.error('Failed to load Firebase config from backend:', error);
            throw new Error('Firebase configuration could not be loaded');
        }
    }

    getFirebaseConfig() {
        return this.firebaseConfig;
    }

    isConfigLoaded() {
        return this.isLoaded && this.firebaseConfig !== null;
    }
}

// Global instance
window.configLoader = new ConfigLoader();

// Helper function for backward compatibility
window.getFirebaseConfig = async function() {
    return await window.configLoader.loadFirebaseConfig();
};