// Firebase configuration loader
class FirebaseConfigLoader {
    constructor() {
        this.config = null;
        this.isLoaded = false;
    }

    async loadConfig() {
        if (this.isLoaded && this.config) {
            return this.config;
        }

        try {
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.config = await response.json();
            this.isLoaded = true;
            
            console.log('Firebase config loaded successfully');
            return this.config;
            
        } catch (error) {
            console.error('Failed to load Firebase config:', error);
            
            // Fallback configuration for development
            this.config = {
                apiKey: "demo-api-key",
                authDomain: "demo.firebaseapp.com",
                databaseURL: "https://demo-default-rtdb.firebaseio.com/",
                projectId: "demo-project",
                storageBucket: "demo-project.appspot.com",
                messagingSenderId: "123456789",
                appId: "1:123456789:web:abcdef123456"
            };
            
            console.warn('Using fallback Firebase config');
            return this.config;
        }
    }

    getConfig() {
        return this.config;
    }

    isConfigLoaded() {
        return this.isLoaded && this.config !== null;
    }
}

// Global instance
window.firebaseConfigLoader = new FirebaseConfigLoader();

// Helper function for backward compatibility
window.getFirebaseConfig = async function() {
    return await window.firebaseConfigLoader.loadConfig();
};