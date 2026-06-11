from app import create_app

# Expose `app` at module level so gunicorn can find it:
#   gunicorn "run:app"
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
