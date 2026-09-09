
    function togglePassword(idInput) {
        const input = document.getElementById(idInput);
        const icon = document.getElementById('toggleIcon');

        if (!input || !icon) return;

        if (input.type === "password") {
            input.type = "text";
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        } else {
            input.type = "password";
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
