import type { BoardViewModel } from '../contract/viewModel';

interface BoardProps {
  board: BoardViewModel;
}

/**
 * 棋盘。
 * 行列数完全来自 snapshot.board.rows / board.cols，不硬编码 5×5。
 * 公共坐标 1-based、row 1 在顶部、col 1 在左侧；
 * 0-based 数组索引只存在于 adapter 与这里的渲染边界。
 */
export function Board({ board }: BoardProps) {
  return (
    <section className="board" aria-label="棋盘">
      <div
        className="board__grid"
        data-testid="board-grid"
        data-rows={board.rows}
        data-cols={board.cols}
        style={{ gridTemplateColumns: `repeat(${board.cols}, minmax(0, 1fr))` }}
      >
        {board.cells.map((rowCells) =>
          rowCells.map((cell) => {
            const isRed = cell.team === 'RED';
            const isBlue = cell.team === 'BLUE';
            const cellClass = [
              'board__cell',
              isRed ? 'board__cell--red' : '',
              isBlue ? 'board__cell--blue' : '',
            ]
              .filter(Boolean)
              .join(' ');
            return (
              <div
                key={`${cell.row}-${cell.col}`}
                className={cellClass}
                data-testid={`cell-${cell.row}-${cell.col}`}
                data-row={cell.row}
                data-col={cell.col}
                data-team={cell.team ?? 'EMPTY'}
              >
                <span className="board__coord">
                  {cell.row},{cell.col}
                </span>
                {cell.team ? (
                  <span className={`unit unit--${cell.team.toLowerCase()}`}>
                    <span className="unit__team">{cell.teamLabel}</span>
                    <span className="unit__hp">生命 {cell.hp}</span>
                  </span>
                ) : null}
              </div>
            );
          }),
        )}
      </div>
    </section>
  );
}
