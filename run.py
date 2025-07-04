from app import create_app

app, socketio = create_app()

if __name__ == '__main__':
    print(f"App listening on port {app.config['PORT']}")
    print(f"Frontend available at: http://localhost:{app.config['PORT']}/app")
    socketio.run(app, host="0.0.0.0", port=app.config['PORT'], debug=True)