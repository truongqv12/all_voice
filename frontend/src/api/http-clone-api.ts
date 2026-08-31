import type { CloneApi } from './clone-api';
import { mockCloneApi } from './clone-api';

export const httpCloneApi: CloneApi = {
  createClone: mockCloneApi.createClone,
  deleteClone: mockCloneApi.deleteClone,
};
