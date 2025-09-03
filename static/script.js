document.addEventListener('DOMContentLoaded', () => {
    console.log('Script yüklendi - DOM hazır');

    /**
     * Gerekli tüm DOM elementlerini tek bir obje içinde toplar.
     */
    const UIElements = {
        authContainer: document.getElementById('auth-container'),
        appContainer: document.getElementById('app-container'),
        loginCard: document.getElementById('login-card'),
        registerCard: document.getElementById('register-card'),
        loginButton: document.getElementById('login-button'),
        loginEmailInput: document.getElementById('login-email'),
        loginPasswordInput: document.getElementById('login-password'),
        loginError: document.getElementById('login-error'),
        registerButton: document.getElementById('register-button'),
        registerEmailInput: document.getElementById('register-email'),
        registerPasswordInput: document.getElementById('register-password'),
        registerError: document.getElementById('register-error'),
        showRegisterLink: document.getElementById('show-register-link'),
        showLoginLink: document.getElementById('show-login-link'),

        // Navigation elements
        navButtons: document.querySelectorAll(
