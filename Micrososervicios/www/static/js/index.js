
        // ===== SILENCIAR ERRORES DE PERMISOS =====
        window.addEventListener('unhandledrejection', function(e) {
            if (e.reason && e.reason.code === 403) {
                e.preventDefault();
                return true;
            }
            if (e.reason && e.reason.message && (
                e.reason.message.includes('permission error') ||
                e.reason.message.includes('permission denied') ||
                e.reason.message.includes('not authorized')
            )) {
                e.preventDefault();
                return true;
            }
        });

        const originalConsoleError = console.error;
        console.error = function() {
            const args = Array.from(arguments);
            const msg = args.join(' ');
            if (msg.includes('permission error') ||
                msg.includes('403') ||
                msg.includes('not authorized') ||
                msg.includes('permission denied')) {
                return;
            }
            originalConsoleError.apply(console, arguments);
        };

        // ===== PROGRESO Y CONTADOR =====
        (function() {
            'use strict';

            function initLoading() {
                try {
                    const progressFill = document.getElementById('progressFill');
                    const progressPercent = document.getElementById('progressPercent');
                    const progressText = document.getElementById('progressText');
                    const countdownNum = document.getElementById('countdownNum');

                    if (!progressFill || !progressPercent || !progressText || !countdownNum) {
                        return;
                    }

                    let progress = 0;
                    let countdown = 3;
                    let phase = 0;
                    let progressInterval = null;
                    let countdownInterval = null;

                    const messages = [
                        'Cargando módulos...',
                        'Conectando base de datos...',
                        'Inicializando ventas...',
                        '¡Listo! 🙏'
                    ];

                    function clearIntervals() {
                        if (progressInterval) clearInterval(progressInterval);
                        if (countdownInterval) clearInterval(countdownInterval);
                    }

                    progressInterval = setInterval(() => {
                        try {
                            let increment;
                            if (progress < 30) increment = 3 + Math.random() * 5;
                            else if (progress < 70) increment = 2 + Math.random() * 3;
                            else increment = 1 + Math.random() * 2;

                            progress = Math.min(progress + increment, 100);

                            progressFill.style.width = progress + '%';
                            progressPercent.textContent = Math.floor(progress) + '%';

                            const phaseIndex = Math.floor(progress / 33);
                            if (phaseIndex > phase && phaseIndex < 3) {
                                phase = phaseIndex;
                                progressText.textContent = messages[phase];
                            }

                            if (progress >= 100) {
                                progressFill.style.width = '100%';
                                progressText.textContent = messages[3];
                                clearInterval(progressInterval);
                            }
                        } catch (e) {}
                    }, 150);

                    countdownInterval = setInterval(() => {
                        try {
                            countdown--;
                            countdownNum.textContent = countdown;

                            countdownNum.style.transform = 'scale(0.8)';
                            setTimeout(() => {
                                countdownNum.style.transform = 'scale(1)';
                            }, 150);

                            if (countdown <= 0) {
                                clearIntervals();
                                const screen = document.getElementById('loadingScreen');
                                if (screen) {
                                    screen.style.transition = 'opacity 0.6s ease';
                                    screen.style.opacity = '0';
                                }
                                setTimeout(() => {
                                    window.location.href = '/catalogo';
                                }, 500);
                            }
                        } catch (e) {}
                    }, 1000);

                    setTimeout(() => {
                        try {
                            if (countdown > 0) {
                                window.location.href = '/catalogo';
                            }
                        } catch (e) {}
                    }, 8000);

                    window.addEventListener('beforeunload', clearIntervals);
                } catch (e) {
                    setTimeout(() => {
                        window.location.href = '/catalogo';
                    }, 3000);
                }
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initLoading);
            } else {
                initLoading();
            }
        })();
    