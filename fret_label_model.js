/* Physical identity never depends on array order. Browser + Node tests. */
(function(root) {
  function number(w) { return w.fret_num ?? w.wire_idx; }
  function add(wires, wire, fretNum) {
    if (!Number.isInteger(fretNum) || fretNum < 0 || fretNum > 36) throw Error('실제 프렛 번호는 0~36 정수여야 합니다.');
    if (wires.some(w => number(w) === fretNum)) throw Error('이미 있는 프렛 번호입니다. 삭제 또는 다른 번호를 선택하세요.');
    return [...wires, {...wire, fret_num:fretNum, wire_idx:fretNum,
      label_id:wire.label_id || ('fret-'+fretNum+'-'+Date.now()), source:wire.source || 'human_manual'}].sort((a,b)=>a.xt-b.xt);
  }
  function remove(wires, fretNum) { return wires.filter(w=>number(w)!==fretNum); }
  function cells(wires) { return wires.slice(1).map((b,i)=>[wires[i],b]).filter(([a,b])=>number(b)===number(a)+1); }
  const api={number,add,remove,cells};
  if(typeof module!=='undefined') module.exports=api;
  root.FretLabels=api;
})(typeof globalThis!=='undefined'?globalThis:this);
