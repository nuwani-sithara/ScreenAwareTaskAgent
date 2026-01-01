def build_game_state(detections: dict) -> dict:
    """
    Converts raw detections into a structured game state
    suitable for agent reasoning.
    """

    board = [[0 for _ in range(4)] for _ in range(4)]

    for tile in detections["tiles"]:
        board[tile["row"]][tile["col"]] = tile["value"]

    return {
        "board": board,
        "tiles": detections["tiles"],     # includes coords + bbox
        "score": detections["score"],
        "best_score": detections["best_score"],
        "button": detections["button"]
    }
