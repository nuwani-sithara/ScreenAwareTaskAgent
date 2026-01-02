def map_tiles_to_grid(tiles, board_bbox):
    bx1, by1, bx2, by2 = board_bbox
    cell_w = (bx2 - bx1) / 4
    cell_h = (by2 - by1) / 4

    grid = [[0]*4 for _ in range(4)]

    for tile in tiles:
        x1, y1, x2, y2 = tile["bbox"]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        col = int((cx - bx1) / cell_w)
        row = int((cy - by1) / cell_h)

        if 0 <= row < 4 and 0 <= col < 4:
            grid[row][col] = tile["value"]

    return grid
