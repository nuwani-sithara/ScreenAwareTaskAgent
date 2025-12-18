from tile_mapper import map_tiles_to_grid

def build_game_state(detections):
    grid = map_tiles_to_grid(
        detections["tiles"],
        detections["board"]["bbox"]
    )

    return {
        "grid": grid,
        "score": detections["score"],
        "best_score": detections["best_score"],
        "buttons": detections["buttons"]
    }
