// ============================================================
// DEMO FILE - INTENTIONALLY BUGGY (for refactor demo video)
// ============================================================
//
// FIX CHECKLIST:
//
// [ ] 1. calculateTotal  -> string concat bug ("100" + "200")
// [ ] 2. getUserById     -> no null check, can return undefined
// [ ] 3. getActiveUsers  -> mutates the input array (sort in place)
// [ ] 4. formatName      -> no trim, crashes on null
// [ ] 5. sumOrders       -> off-by-one (skips last item)
// [ ] 6. processUsers    -> too long, mixes filtering + mapping (SRP)
//
// ============================================================

const users = [
  { id: 1, name: '  Alice  ', active: true, price: '100' },
  { id: 2, name: 'Bob', active: false, price: '200' },
  { id: 3, name: null, active: true, price: '300' },
];

// BUG 1: adds strings instead of numbers
function calculateTotal(items) {
  let total = 0;
  for (let i = 0; i < items.length; i++) {
    total += items[i].price;
  }
  return total;
}

// BUG 2: returns undefined when user not found
function getUserById(id) {
  return users.find((u) => u.id == id);
}

// BUG 3: sort() mutates the caller's array
function getActiveUsers(list) {
  list.sort((a, b) => a.id - b.id);
  return list.filter((u) => u.active);
}

// BUG 4: no trim, throws on null name
function formatName(user) {
  return user.name.toUpperCase();
}

// BUG 5: loop stops one item too early
function sumOrders(orders) {
  let sum = 0;
  for (let i = 0; i < orders.length - 1; i++) {
    sum += orders[i].amount;
  }
  return sum;
}

// BUG 6: does filtering + mapping in one long block
function processUsers(list) {
  const result = [];
  for (let i = 0; i < list.length; i++) {
    const u = list[i];
    if (u.active == true) {
      if (u.name != null) {
        result.push({ id: u.id, name: u.name.trim() });
      }
    }
  }
  return result;
}

module.exports = {
  users,
  calculateTotal,
  getUserById,
  getActiveUsers,
  formatName,
  sumOrders,
  processUsers,
};
