/** The server sent something the client cannot make sense of. Always a bug. */
export class ContractViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractViolation";
  }
}
